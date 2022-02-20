import bpy
from imutils import face_utils
import dlib
import cv2
import time
import numpy
from bpy.props import FloatProperty
    
class OpenCVAnimOperator(bpy.types.Operator):
    #main operator
    bl_idname = "wm.opencv_operator"
    bl_label = "Start MoCap Operator"
     
    #p - trained model
    p = "C:/Users/glebs/PycharmProjects/Deep/shape_predictor_68_face_landmarks.dat" #path to predictor
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(p)

    _timer = None
    _cap  = None
    
    width = 800
    height = 600

    flag = 0

    stop :bpy.props.BoolProperty()
    
    # World coordinate points of 3D model x-y-z
    model_points = numpy.array([
                                (-0.005734, 0.0, 0.586476),             # Nose tip
                                (-0.005734, -0.09531, 0.513174),        # Chin
                                (0.007338, -0.05133, 0.657173),     # Left eye left corner
                                (-0.018807, -0.05133, 0.657173),      # Right eye right corne
                                (0.017974, -0.073097, 0.562466),    # Left Mouth corner
                                (-0.029025, -0.073099, 0.563207)     # Right mouth corner
                            ], dtype = numpy.float32)

    # Camera matrix
    camera_matrix = numpy.array(
                            [[height, 0.0, width/2],
                            [0.0, height, height/2],
                            [0.0, 0.0, 1.0]], dtype = numpy.float32
                            )
    
    # Calculate moving average to reduce shaking of points
    def smooth_value(self, name, length, value):
        if not hasattr(self, 'smooth'): #create smooth attribute for class if theres none
            self.smooth = {}
        if not name in self.smooth:
            self.smooth[name] = numpy.array([value])
        else:
            self.smooth[name] = numpy.insert(arr=self.smooth[name], obj=0, values=value)
            if self.smooth[name].size > length:
                self.smooth[name] = numpy.delete(self.smooth[name], self.smooth[name].size-1, 0)
        sum = 0
        for val in self.smooth[name]:
            sum += val
        return sum / self.smooth[name].size


	#Keeps min and max values, then returns the value in a range 0 - 1
    def get_range(self, name, value):
        print(name, " value = " + str(value))
        if not hasattr(self, 'range'):
            self.range = {}
        if not name in self.range:
            self.range[name] = numpy.array([value, value])
        else:
            self.range[name] = numpy.array([min(value, self.range[name][0]), max(value, self.range[name][1])] )
        val_range = self.range[name][1] - self.range[name][0]
        if val_range != 0:
            print((value - self.range[name][0]) / val_range)
            return (value - self.range[name][0]) / val_range
        else:
            return 0

    def modal(self, context, event):

        if (event.type in {'RIGHTMOUSE', 'ESC'}) or self.stop == True:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            self.init_camera()
            _, image = self._cap.read()
            image = cv2.flip(image, 1)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            rects = self.detector(gray, 0)
            # bpy.context.scene.frame_set(frame_num)
         
            # For each detected face, find the landmark.
            for (i, rect) in enumerate(rects):
                shape = self.predictor(gray, rect)
                shape = face_utils.shape_to_np(shape)
             
                #2D image points. If you change the image, you need to change vector
                image_points = numpy.array([shape[30],     # Nose tip - 31
                                            shape[8],      # Chin - 9
                                            shape[36],     # Left eye left corner - 37
                                            shape[45],     # Right eye right corne - 46
                                            shape[48],     # Left Mouth corner - 49
                                            shape[54]     # Right mouth corner - 55
                                        ], dtype = numpy.float32)
             
                dist_coeffs = numpy.zeros((4,1)) # Assuming no lens distortion
             
                if hasattr(self, 'rotation_vector'):
                    (success, self.rotation_vector, self.translation_vector) = cv2.solvePnP(self.model_points, 
                        image_points, self.camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE, 
                        rvec=self.rotation_vector, tvec=self.translation_vector, 
                        useExtrinsicGuess=True)
                else:
                    (success, self.rotation_vector, self.translation_vector) = cv2.solvePnP(self.model_points, 
                        image_points, self.camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE, 
                        useExtrinsicGuess=False)
             
                if not hasattr(self, 'first_angle'):
                    self.first_angle = numpy.copy(self.rotation_vector)
             
                bones = bpy.data.objects["armature_Danny"].pose.bones
                
                bones["spine_3"].rotation_euler[0] = self.smooth_value("h_x", 3, (self.rotation_vector[0] - self.first_angle[0])) / -bpy.context.scene.my_tool.y_int   # left/right tilt
                bones["spine_3"].rotation_euler[1] = self.smooth_value("h_y", 3, -(self.rotation_vector[1] - self.first_angle[1])) / -bpy.context.scene.my_tool.x_int  # Turn head around your axis
                #bones["spine_3"].rotation_euler[2] = self.smooth_value("h_z", 3, (self.rotation_vector[2] - self.first_angle[2])) / -bpy.context.scene.my_tool.x_int   # Turn head up/down
#                
                bones["jaw_parent"].location[2] = self.smooth_value("j_p", 3, -self.get_range("mouth_height", numpy.linalg.norm(shape[62] - shape[66])) * 0.06 )
                bones["mouth_SKC.R"].location[0] = self.smooth_value("m_r", 3, -(self.get_range("mouth_right", numpy.linalg.norm(shape[54] - shape[48])) - 0.5) * -0.04)
                bones["mouth_SKC.L"].location[0] = self.smooth_value("m_l", 3, (self.get_range("mouth_left", numpy.linalg.norm(shape[54] - shape[48])) - 0.5) * -0.04)
                bones["mouth_SKC.L"].location[2] = bones["mouth_SKC.R"].location[2] = self.smooth_value("m_r", 3, -(self.get_range("mouth_right", numpy.linalg.norm(shape[54] - shape[48])) - 0.5) * -0.04)
                bones["brow_inner_SKC.R"].location[2] = self.smooth_value("b_r", 3, (self.get_range("brow_right", numpy.linalg.norm(shape[19] - shape[27])) -0.5) * 0.04)
                bones["brow_inner_SKC.L"].location[2] = self.smooth_value("b_l", 3, (self.get_range("brow_left", numpy.linalg.norm(shape[24] - shape[27])) -0.5) * 0.04)
                bones["jaw"].location[2] = self.smooth_value("j_j", 2, -self.get_range("jaw_height", numpy.linalg.norm(shape[62] - shape[66])) * 0.03 )
                bones["cheek.R"].location[0] = self.smooth_value("m_r", 2, -(self.get_range("mouth_right", numpy.linalg.norm(shape[54] - shape[48])) - 0.5) * -0.04)
                bones["cheek.L"].location[0] = self.smooth_value("m_l", 2, (self.get_range("mouth_left", numpy.linalg.norm(shape[54] - shape[48])) - 0.5) * -0.04)
                # eyelids                
                l_open = self.smooth_value("e_l", 2, self.get_range("l_open", -numpy.linalg.norm(shape[48] - shape[44]))  )
                r_open = self.smooth_value("e_r", 2, self.get_range("r_open", -numpy.linalg.norm(shape[41] - shape[39]))  )
                eyes_open = (l_open + r_open) / 2.0 # looks weird if both eyes aren't the same...
                bones["eyelid_upper_CTRL.R"].location[2] =   -eyes_open * 0.1 + 0.005
                bones["eyelid_lower_CTRL.R"].location[2] =  eyes_open * 0.1 - 0.005
                bones["eyelid_upper_CTRL.L"].location[2] =   -eyes_open * 0.1 + 0.005
                bones["eyelid_lower_CTRL.L"].location[2] =  eyes_open * 0.1 - 0.005
				
				# record bone keyframes
                bones["spine_3"].keyframe_insert(data_path="rotation_euler", index=-1)
                bones["jaw_parent"].keyframe_insert(data_path="location", index=-1)
                bones["mouth_SKC.R"].keyframe_insert(data_path="location", index=-1)
                bones["mouth_SKC.L"].keyframe_insert(data_path="location", index=-1)
                bones["brow_inner_SKC.R"].keyframe_insert(data_path="location", index=-1)
                bones["brow_inner_SKC.L"].keyframe_insert(data_path="location", index=-1)
                bones["jaw"].keyframe_insert(data_path="location", index=-1)
                bones["cheek.R"].keyframe_insert(data_path="location", index=-1)
                bones["cheek.L"].keyframe_insert(data_path="location", index=-1)
                bones["eyelid_upper_CTRL.R"].keyframe_insert(data_path="location", index=-1)
                bones["eyelid_lower_CTRL.R"].keyframe_insert(data_path="location", index=-1)
                bones["eyelid_upper_CTRL.L"].keyframe_insert(data_path="location", index=-1)
                bones["eyelid_lower_CTRL.L"].keyframe_insert(data_path="location", index=-1)
         
                for (x, y) in shape:
                    cv2.circle(image, (x, y), 2, (0, 255, 255), -1)
                 
            cv2.imshow("Output", image)
            cv2.waitKey(1)

        return {'PASS_THROUGH'}
    
    def init_camera(self):
        if self._cap == None:
            self._cap = cv2.VideoCapture(0)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(0.5)
    
    def stop_playback(self, scene):
        print(format(scene.frame_current) + " / " + format(scene.frame_end))
        if scene.frame_current == scene.frame_end:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        
    def execute(self, context):
        bpy.app.handlers.frame_change_pre.append(self.stop_playback)

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        cv2.destroyAllWindows()
        self._cap.release()
        self._cap = None

def register():
    bpy.utils.register_class(OpenCVAnimOperator)

def unregister():
    bpy.utils.unregister_class(OpenCVAnimOperator)

if __name__ == "__main__":
    register()

    # test call
    #bpy.ops.wm.opencv_operator()
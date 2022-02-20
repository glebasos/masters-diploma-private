bl_info = {
    "name": "Motion CapturemDiploma Addon",
    "description": "",
    "author": "SUAI4642",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}


import bpy

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )

class MyProperties(PropertyGroup):

    x_int: FloatProperty(
        name = "X coefficient",
        description="X influence coefficient",
        default = 1,
        min = 0.1,
        max = 10
        )
        
    y_int: FloatProperty(
        name = "Z coefficient",
        description="Y influence coefficient",
        default = 1,
        min = 0.1,
        max = 10
        )

class WM_OT_ResetBones(Operator):
    bl_label = "Reset Bones"
    bl_idname = "wm.reset_bone_position"
    bl_description = "Set local location and rotation to 0"

    def execute(self, context):
        ob = bpy.data.objects['armature_Danny']
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='POSE')
        flag = 0
    
        for pbone in bpy.context.active_object.pose.bones:
            pbone.location = (0, 0, 0)
            pbone.rotation_euler[0] = 0
            pbone.rotation_euler[1] = 0
            pbone.rotation_euler[2] = 0
        
        return {'FINISHED'}


class OBJECT_PT_CustomPanel(Panel):
    #Creates a Panel in the Object properties window

    bl_label = "MoCap settings"
    bl_idname = "OBJECT_PT_custom_panel"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "MoCap"
    bl_context = "posemode"   
    # bl_label = "MoCap"
    # bl_space_type = 'VIEW_3D'
    # bl_context_mode='OBJECT'
        
    # #bl_region_type = 'TOOLS'
    # bl_idname = "ui_plus.opencv"
    # #bl_context = "object"
    # bl_options = {'REGISTER'}

    # bl_icon = "ops.generic.select_circle"

    @classmethod
    def poll(self,context):
        return context.object is not None
        
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool


        layout.prop(mytool, "x_int")
        layout.prop(mytool, "y_int")
        layout.separator()
        layout.operator("wm.reset_bone_position")
        layout.separator()
        layout.operator("wm.opencv_operator")
        layout.separator()
        #props = tool.operator_properties("wm.opencv_operator")
        #layout.prop(props, "stop", text="Stop Capture")
        #layout.prop(tool.op, "stop", text="Stop Capture")

classes = (
    MyProperties,
    WM_OT_ResetBones,
    OBJECT_PT_CustomPanel
)

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.my_tool = PointerProperty(type=MyProperties)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.my_tool



if __name__ == "__main__":
    register()
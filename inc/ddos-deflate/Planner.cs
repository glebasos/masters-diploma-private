using Google.OrTools.Sat;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace PlanServer.Models
{
    public static class Planner
    {
        private static IEnumerable<DateTime> EachDay(DateTime from, DateTime thru)
        {
            for (var day = from.Date; day.Date <= thru.Date; day = day.AddDays(1))
                yield return day;
        }
        public static async Task<List<OrToolsJob>> OROptimizeAsync(int horizon, List<int> workers, List<int> workers_job_num, List<int> job_types, List<int> job_type_num, List<OrToolsJob> jobs, DateTime reftime, DateTime lastday)
        {
            List<OrToolsJob> result = await Task.Run(() => OROptimize(horizon, workers, workers_job_num, job_types, job_type_num, jobs, reftime, lastday));
            return result;
        }
        private static List<OrToolsJob> OROptimize(int horizon, List<int> workers, List<int> workers_job_num, List<int> job_types, List<int> job_type_num, List<OrToolsJob> jobs, DateTime reftime, DateTime lastday)
        {
            Console.WriteLine("Defining model");
            CpModel model = new CpModel();
            List<List<List<IntervalVar>>> intervals_by_worker = new();
            List<List<List<BoolVar>>> bools_by_worker = new();
            List<List<List<IntVar>>> start_by_worker = new();
            List<List<List<IntVar>>> end_by_worker = new();
            List<List<List<int>>> corresponding_jobtype_worker = new();
            foreach (var w in workers)
            {
                List<List<IntervalVar>> intervals_by_type = new();
                List<List<BoolVar>> bools_by_type = new();
                List<List<IntVar>> start_by_type = new();
                List<List<IntVar>> end_by_type = new();
                List<List<int>> corresponding_jobtype_type = new();
                foreach (var jt in job_types)
                {
                    List<IntervalVar> intervals_by_job_by_type = new();
                    List<BoolVar> bools_by_job_by_type = new();
                    List<IntVar> start_by_job_by_type = new();
                    List<IntVar> end_by_job_by_type = new();
                    List<int> corresponding_jobtype_job = new();
                    foreach (var job in jobs)
                    {
                        if (jt == job.Type && w == job.WorkerID)
                        {
                            var performed_at = model.NewBoolVar($"performed by {w}wID {jt}type {job.ID}jID");
                            var start = model.NewIntVar(0, horizon, $"start of X {jt} {job.ID}");
                            var end = model.NewIntVar(0, horizon, $"end of {w} {jt} {job.ID}");
                            var optint = model.NewOptionalIntervalVar(start, job.TimeSpanMinutes, end, performed_at, $"interval of {w} {jt} {job.ID}");
                            model.Add(start < end);
                            bools_by_job_by_type.Add(performed_at);
                            intervals_by_job_by_type.Add(optint);
                            start_by_job_by_type.Add(start);
                            end_by_job_by_type.Add(end);
                            corresponding_jobtype_job.Add(job.ID);
                        }
                    }
                    intervals_by_type.Add(intervals_by_job_by_type);
                    bools_by_type.Add(bools_by_job_by_type);
                    start_by_type.Add(start_by_job_by_type);
                    end_by_type.Add(end_by_job_by_type);
                    corresponding_jobtype_type.Add(corresponding_jobtype_job);
                }
                intervals_by_worker.Add(intervals_by_type);
                bools_by_worker.Add(bools_by_type);
                start_by_worker.Add(start_by_type);
                end_by_worker.Add(end_by_type);
                corresponding_jobtype_worker.Add(corresponding_jobtype_type);

            }
            Console.WriteLine("Model defined");
            ///////////////////////////////////////////////////////
            ///
            //работы по рабочему
            List<List<IntervalVar>> jobIntervals_by_worker = new();
            foreach (var w in intervals_by_worker)
            {
                //List<IntervalVar> lst = new();
                var flatlist = w.SelectMany(i => i).ToList();
                jobIntervals_by_worker.Add(flatlist);
            }

            //определим нерабочие (ночные интервалы) - допустим с 9 утра до 9 вечера
            //даты планирования выбираются с 00:00 по 00:00
            //отсюда каждый день можно без проблем на N смен (зависят от типа работы/рабочего - ?)
            //0 + 540 => ночь; +720 => день; + 180 => остатки ночи
            List<IntervalVar> sleepIntervals = new();
            int dayCounter = 0;

            foreach (DateTime day in EachDay(reftime, lastday))
            {

                int st = dayCounter * 1440;
                
                if ((day.DayOfWeek == DayOfWeek.Saturday) || (day.DayOfWeek == DayOfWeek.Sunday))
                {
                    //по выходным не работаем
                    int fin1 = st + 1440;
                    var siSS = model.NewIntervalVar(st, 1440, fin1, $"sat/sun {dayCounter}");
                    sleepIntervals.Add(siSS);
                }
                else
                {
                    //по будням - с 9 до 9
                    int fin = st + 540;
                    var si = model.NewIntervalVar(st, 540, fin, $"sleep 1 of day {dayCounter}");
                    sleepIntervals.Add(si);
                    st = fin + 720; //пропускаем рабочие 12 часов
                    fin = st + 180;
                    //второй ночной интервал
                    var si2 = model.NewIntervalVar(st, 180, fin, $"sleep 2 of day {dayCounter}");
                    sleepIntervals.Add(si2);
                }
                
                dayCounter++;
            }


            //работы одного рабочего не пересекаются
            foreach (var ji in jobIntervals_by_worker)
            {
                ji.AddRange(sleepIntervals);
                model.AddNoOverlap(ji);
            }


            ///////////////////////////////////////////
            ///разделяем работы по типу работы
            ///
            List<List<IntervalVar>> jobIntervals_by_type = new();

            foreach (var t in job_types)
            {
                List<IntervalVar> jlst = new();
                jobIntervals_by_type.Add(jlst);
            }

            foreach (var i_worker in intervals_by_worker)
            {
                for (int i_type = 0; i_type < i_worker.Count; i_type++)
                {
                    var jflatlist = i_worker[i_type];
                    jobIntervals_by_type[i_type].AddRange(jflatlist);
                }

            }

            //для каждого типа работы - все работы не пересекаются
            foreach (var ji in jobIntervals_by_type)
            {
                
                model.AddNoOverlap(ji);
            }

            ////////////////////////////////////////////
            ///разделяем performed_at по типам работы
            Console.WriteLine("разделяем performed_at по типам работы");
            List<List<BoolVar>> performedAt_by_type = new();

            foreach (var t in job_types)
            {
                List<BoolVar> perflist = new();
                performedAt_by_type.Add(perflist);
            }

            foreach (var b_worker in bools_by_worker)
            {
                for (int b_type = 0; b_type < b_worker.Count; b_type++)
                {
                    var flatperf = b_worker[b_type];
                    performedAt_by_type[b_type].AddRange(flatperf);
                }
            }
            for (int i = 0; i < performedAt_by_type.Count; i++)
            {
                model.Add(LinearExpr.Sum(performedAt_by_type[i]) <= job_type_num[i]);
            }
            //////////////////////////////////
            ///разделяем performed_at по рабочим
            List<List<BoolVar>> performedAt_by_worker = new();

            foreach (var t in bools_by_worker)
            {
                //List<IntVar> worklist = new();
                var flatwork = t.SelectMany(i => i).ToList(); ;
                performedAt_by_worker.Add(flatwork); ;
            }


            //для каждого рабочего колво работ запланированных <= необходимому
            for (int i = 0; i < performedAt_by_worker.Count; i++)
            {
                model.Add(LinearExpr.Sum(performedAt_by_worker[i]) <= workers_job_num[i]);
            }

            /////////////////////////////
            ///
            //разделим старты и концы работ по типам
            List<List<IntVar>> startAt_by_type = new();

            foreach (var t in job_types)
            {
                List<IntVar> perflist = new();
                startAt_by_type.Add(perflist);
            }

            foreach (var s_worker in start_by_worker)
            {
                for (int s_type = 0; s_type < s_worker.Count; s_type++)
                {
                    var flatstart = s_worker[s_type];
                    startAt_by_type[s_type].AddRange(flatstart);
                }
            }

            List<List<IntVar>> endAt_by_type = new();

            foreach (var t in job_types)
            {
                List<IntVar> perflist = new();
                endAt_by_type.Add(perflist);
            }

            foreach (var s_worker in end_by_worker)
            {
                for (int s_type = 0; s_type < s_worker.Count; s_type++)
                {
                    var flatend = s_worker[s_type];
                    endAt_by_type[s_type].AddRange(flatend);
                }
            }

            //соблюдай-ка порядок работ
            //проходим все типы работ что попались
            for (int k = 0; k < startAt_by_type.Count; k++)
            {
                string varname = startAt_by_type[k][0].Name();
                varname = varname.Substring(11, 1);
                //если тип третий
                if (Int32.Parse(varname) == 3)
                {
                    //foreach (var s in startAt_by_type[k])
                    //{

                    //}
                    for (int i = 0; i < startAt_by_type[k].Count - 1; i++)
                    {
                        model.Add(startAt_by_type[k][i + 1] > endAt_by_type[k][i]);
                    }
                }
            }

            //для третьего типа(плановая работа) - работы не чаще раза в день
            for (int k = 0; k < startAt_by_type.Count; k++)
            {
                string varname = startAt_by_type[k][0].Name();
                string secondvarname = varname;
                varname = varname.Substring(11, 1);
                //если тип третий
                if (varname == " ")
                {
                    varname = secondvarname.Substring(11, 2);
                }
                if (Int32.Parse(varname) == 3 || Int32.Parse(varname) == 13)
                {
                    for (int i = 0; i < startAt_by_type[k].Count - 1; i++)
                    {
                        model.Add(startAt_by_type[k][i + 1] - endAt_by_type[k][i] >= 1440).OnlyEnforceIf(performedAt_by_type[k][i]);
                        //model.Add(startAt_by_type[k][i + 1] > endAt_by_type[k][i]);
                    }
                }
            }



            ///////////////////////////

            var flatbools = bools_by_worker.SelectMany(i => i).SelectMany(i => i);
            Console.WriteLine("Starting Optimization at:");
            Console.WriteLine(DateTime.Now.ToString("MM/dd/yyyy HH:mm:ss"));
            //целевая функция - максимизировать количество работ
            model.Maximize(LinearExpr.Sum(flatbools));
            //Console.WriteLine("test");
            var solver = new CpSolver();
            solver.StringParameters = "num_search_workers:1";
            var status = solver.Solve(model);

            Console.WriteLine("#########################");
            Console.WriteLine("Всего работ:" + jobs.Count.ToString());
            Console.WriteLine("Распределено работ: " + solver.ObjectiveValue);
            Console.WriteLine("#########################");

            List<OrToolsJob> PlannedJobs = new();

            //принтим если есть решение
            if (status == CpSolverStatus.Feasible || status == CpSolverStatus.Optimal || status == CpSolverStatus.Unknown)
            {
                for (int w = 0; w < workers.Count; w++)
                {

                    for (int jt = 0; jt < job_types.Count; jt++)
                    {

                        for (int job = 0; job < bools_by_worker[w][jt].Count; job++)
                        {
                            //Console.WriteLine(bools_by_hour[i][j][k].Count());
                            //Console.WriteLine("----------");
                            if (solver.Value(bools_by_worker[w][jt][job]) == 1)
                            {
                                PlannedJobs.Add(new OrToolsJob(corresponding_jobtype_worker[w][jt][job], job_types[jt], (int)solver.Value(start_by_worker[w][jt][job]), (int)solver.Value(end_by_worker[w][jt][job]), reftime, workers[w]));
                                //для каждого воркера, каждый джобтайп, каждая работа конкретного типа - начало + конец
                            }
                        }
                    }

                }

            }
            Console.WriteLine("Finished at:");
            Console.WriteLine(DateTime.Now.ToString("MM/dd/yyyy HH:mm:ss"));
            return PlannedJobs;
        }
    }
}

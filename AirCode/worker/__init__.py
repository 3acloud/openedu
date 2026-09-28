import os
import re
import shutil
import time
import json
import inspect
import threading
from utilities.ask_answer import Answer, SetSocketName, subworkflows, threadLock, pauseworkflows, triggerworkflows, backworkflows

import asyncio
from utilities.ask_answer import Ask, Finish
from utilities.workflow import Workflow
from worker.tasks import (
    llms,
    tools,
    output,
    text_processing,
)


task_functions = {}
task_modules = [
    llms,
    tools,
    output,
    text_processing,
]
for module in task_modules:
    functions = {}
    module_name = module.__name__.split(".")[-1]
    for name, obj in inspect.getmembers(module):
        if (
            callable(obj)
            and not inspect.isclass(obj)
            and not inspect.ismethod(obj)
            and obj.__class__.__name__ == "Task"
        ):
            functions[name] = obj
    task_functions[module_name] = functions

func_list = []
data_list = []

def main_worker(threadtimes: dict):
   lasttime = time.time()
   while True:
      try:
         threadtimes[threading.current_thread().ident] = time.time()

         workflow = None
         workflow_data = None
         if time.time() - lasttime > 0.5:
            threadLock.acquire()
            i = 0
            while i < len(pauseworkflows):
               [pauseworkflow, node_id, task_name, pausetime] = pauseworkflows[i]
               if time.time() - pausetime > 10:
                  workflow = pauseworkflow
                  workflow_data = workflow.data
                  pauseworkflows.remove(pauseworkflows[i])
                  break
               i += 1
            i = 0
            while i < len(triggerworkflows):
               [triggerworkflow, node_id, pausetime] = triggerworkflows[i]
               if pausetime == 0:
                  workflow = triggerworkflow
                  workflow_data = workflow.data
                  triggerworkflows.remove(triggerworkflows[i])
                  break
               if time.time() - pausetime > 3600:
                  triggerworkflows.remove(triggerworkflows[i])
                  break
               i += 1
            if workflow == None:
               i = 0
               while i < len(subworkflows):
                  [mainworkflow, node_id, zll, subhandle, state] = subworkflows[i]
                  if state == 0:
                     workflow = mainworkflow
                     workflow_data = workflow.data
                     subworkflows.remove(subworkflows[i])
                     break
                  i += 1
            threadLock.release()
            lasttime = time.time()
         if workflow == None:
            ask_data, handle = Ask()
            if len(ask_data) == 0:
               time.sleep(0.01)
               continue
            if str(handle) != "":
               try:
                  os.mkdir("SERVERFILES/" + str(handle))
               except Exception:
                  pass
            askjson = ask_data
            try:
               askjson = re.sub("\t", "    ", askjson)
               ask_data = json.loads(askjson)
            except Exception as e:
               print(f"json错误: {str(e)}")
               print(askjson)
               Finish(handle)
               try:
                  shutil.rmtree("SERVERFILES/" + str(handle))
               except Exception:
                  pass
               continue
            try:
               username = ask_data["username"]
            except Exception:
               username = ""
            try:
               userrank = int(ask_data["userrank"])
            except Exception:
               userrank = 0
            try:
               userowner = ask_data["userowner"]
            except Exception:
               userowner = ""
            try:
               version = int(ask_data["version"])
            except Exception:
               version = 0
            try:
               debug = int(ask_data["debug"])
            except Exception:
               debug = 0
            try:
               streamrunid = ask_data["streamrunid"]
            except Exception:
               streamrunid = ""
            try:
               streamgetid = ask_data["streamgetid"]
            except Exception:
               streamgetid = ""
            if streamgetid != "":
               backtext = []
               tempfiles = []
               finished = False
               existed = False
               threadLock.acquire()
               i = 0
               while i < len(backworkflows):
                  [streamid, backtext, tempfiles, backhandle, state, username, createtime] = backworkflows[i]
                  if streamid == streamgetid:
                     existed = True
                  if streamid == streamgetid and (state == 1 or (time.time() - createtime) > 86400):
                     backworkflows.remove(backworkflows[i])
                     finished = True
                     break
                  i += 1
               threadLock.release()
               if finished:
                  i = 0
                  while i < len(backtext):
                     Answer(backtext[i], handle, "")
                     i += 1
                  Answer(streamgetid, handle, "")
                  try:
                     shutil.rmtree("SERVERFILES/" + str(handle))
                  except Exception:
                     pass
                  for tempfile in tempfiles:
                     try:
                        if os.path.exists(tempfile):
                           os.remove(tempfile)
                     except Exception:
                        pass
               if not existed:
                  Answer(streamgetid, handle, "")
               SetSocketName(username, handle)
               Finish(handle, "")
               continue
            if streamrunid != "":
               SetSocketName(username, handle)
               Finish(handle, "")
               threadLock.acquire()
               backworkflows.append([streamrunid, [], [], handle, 0, username, time.time()])
               threadLock.release()
            workflow_data = {"wid": handle,"answered":False}
            workflow_data["username"] = username
            workflow_data["userrank"] = userrank
            workflow_data["userowner"] = userowner
            workflow_data["streamrunid"] = streamrunid
            workflow_data["version"] = version
            workflow_data["debug"] = debug
            workflow_data["edges"] = []
            workflow_data["tempfiles"] = []
            nodes = []
            for node in ask_data["nodes"]:
               type = ""
               category = ""
               match node["type"]:
                  case "语言模型":
                     category = "llms"
                     type = "l_ai"
                  case "生成图片":
                     category = "llms"
                     type = "image_ai"
                  case "文本合成":
                     category = "text_processing"
                     type = "template_compose"
                  case "任务智能体":
                     category = "tools"
                     type = "task_agent"
                  case "代码解释器":
                     category = "tools"
                     type = "code_interpreter"
                  case "输出文本":
                     category = "output"
                     type = "text"
                  case "输出文档":
                     category = "output"
                     type = "document"
                  case "输出音频":
                     category = "output"
                     type = "voice"
               if type == "":
                  continue
               item = {}
               item["id"] = node["name"]
               item["type"] = type
               item["category"] = category
               itemdata = {}
               itemdata["task_name"] = category + "." + type
               outtemplate = {}
               itemdata["outtemplate"] = outtemplate
               if "output" in node:
                  for fname, fvalue in node["output"].items():
                     field = {}
                     field["value"] = fvalue
                     field["type"] = "str"
                     field["list"] = False
                     field["field_type"] = ""
                     outtemplate[fname] = field
               template = {}
               itemdata["template"] = template
               if type == "call_workflow":
                  field = {}
                  field["value"] = "-1"
                  field["type"] = "str"
                  field["list"] = False
                  field["field_type"] = ""
                  template["index"] = field
               for fname, fvalue in node["input"].items():
                  field = {}
                  field["value"] = fvalue
                  field["type"] = "str"
                  field["list"] = False
                  field["field_type"] = ""
                  template[fname] = field
                  pos = str(fvalue).find(".")
                  if pos >= 0:
                     fl = [fvalue[:pos], fvalue[pos+1:]]
                     fl[0] = fvalue[:pos]
                     fl[1] = fvalue[pos+1:]
                  else:
                     fl = [fvalue]
                  if len(fl) == 2:
                     for nd in ask_data["nodes"]:
                        if nd["name"] == fl[0]:
                           for fn, fv in nd["output"].items():
                              if (fn == fl[1]):
                                 edge = {}
                                 edge["source"] = nd["name"]
                                 edge["sourceHandle"] = fn
                                 edge["target"] = node["name"]
                                 edge["targetHandle"] = fname
                                 workflow_data["edges"].append(edge)
                                 break
                           for fn, fv in nd["input"].items():
                              if (fn == fl[1]):
                                 edge = {}
                                 edge["source"] = nd["name"]
                                 edge["sourceHandle"] = fn
                                 edge["target"] = node["name"]
                                 edge["targetHandle"] = fname
                                 workflow_data["edges"].append(edge)
                                 break
                           break
               item["data"] = itemdata
               nodes.append(item)
            workflow_data["nodes"] = nodes
            workflow_data["nodesrun"] = []
            workflow_data["nodesdone"] = []
            workflow = Workflow(workflow_data)

            if (handle < 0):
               threadLock.acquire()
               i = 0
               while i < len(subworkflows):
                  [mainworkflow, node_id, zll, subhandle, state] = subworkflows[i]
                  if handle == subhandle:
                     index = int(mainworkflow.get_node_field_value(node_id, "index"))
                     fields = mainworkflow.get_node_fields(node_id)
                     for field in fields:
                        if field in ("指令流", "index"):
                           continue
                        for item in nodes:
                           if item["type"] == "form_trigger" or item["type"] == "prompt_trigger" or item["type"] == "text_trigger" or item["type"] == "file_trigger":
                              fieldvalue = mainworkflow.get_node_field_value(node_id, field)
                              if isinstance(fieldvalue, list):
                                 fieldvalue = fieldvalue[index] if index < len(fieldvalue) else None
                              workflow.update_node_field_value(item["id"], field, fieldvalue)
                           else:
                              for nd in ask_data["nodes"]:
                                 if nd["name"] == item["id"]:
                                    for fn, fv in nd["input"].items():
                                       if nd["name"] + "." + fn == field and fv == "":
                                          fieldvalue = mainworkflow.get_node_field_value(node_id, field)
                                          if isinstance(fieldvalue, list):
                                             fieldvalue = fieldvalue[index] if index < len(fieldvalue) else None
                                          workflow.update_node_field_value(item["id"], fn, fieldvalue)
                                    break
                     break
                  i += 1
               threadLock.release()

         sorted_tasks = workflow.get_sorted_task_order()
         count = 0
         tContinue = False
         tChanged = True
         while True:
            if count == len(sorted_tasks):
               break

            tBreak = False
            threadLock.acquire()
            i = 0
            while i < len(pauseworkflows):
               [pauseworkflow, node_id, task_name, pausetime] = pauseworkflows[i]
               if pauseworkflow.data["wid"] == workflow.data["wid"]:
                  tBreak = True
               if tBreak:
                  break
               i += 1
            threadLock.release()
            if tBreak:
               tContinue = True
               break

            tBreak = False
            threadLock.acquire()
            i = 0
            while i < len(triggerworkflows):
               [triggerworkflow, node_id, pausetime] = triggerworkflows[i]
               if triggerworkflow.data["wid"] == workflow.data["wid"]:
                  tBreak = True
               if tBreak:
                  break
               i += 1
            threadLock.release()
            if tBreak:
               tContinue = True
               break

            tBreak = False
            threadLock.acquire()
            i = 0
            while i < len(subworkflows):
               [mainworkflow, node_id, zll, subhandle, state] = subworkflows[i]
               if mainworkflow.data["wid"] == workflow.data["wid"]:
                  tBreak = True
               if tBreak:
                  break
               i += 1
            threadLock.release()
            if tBreak:
               tContinue = True
               break

            if tChanged:
               tChanged = False
               threadLock.acquire()
               for task in sorted_tasks:
                  if task in workflow_data["nodesrun"]:
                     continue
                  income = False
                  for edge in workflow.edges:
                     if edge["target"] == task["node_id"]:
                        if edge["source"] not in workflow_data["nodesdone"]:
                           income = True
                           break
                  if income:
                     continue
                  module, function = task["task_name"].split(".")
                  func_list.append(task_functions[module][function].s(task["node_id"]))
                  data_list.append(workflow_data)
                  workflow_data["nodesrun"].append(task)
               threadLock.release()
            threadLock.acquire()
            tdcount = len(workflow_data["nodesdone"])
            threadLock.release()
            if count != tdcount:
               count = tdcount
               tChanged = True
            else:
               time.sleep(0.01)
            if time.time() - threadtimes[threading.current_thread().ident] > 86400:
               Finish(workflow_data["wid"], workflow_data["streamrunid"])
               break
         if tContinue:
            continue

         Finish(workflow_data["wid"], workflow_data["streamrunid"])
         threadLock.acquire()
         i = 0
         tContinue = False
         while i < len(backworkflows):
            [streamid, backtext, tempfiles, backhandle, state, username, createtime] = backworkflows[i]
            if workflow_data["wid"] == backhandle:
               for tempfile in workflow_data["tempfiles"]:
                  tempfiles.append(tempfile)
               tContinue = True
               break
            i += 1
         threadLock.release()
         if tContinue:
            continue
         try:
            shutil.rmtree("SERVERFILES/" + str(workflow_data["wid"]))
         except Exception:
            pass
         for tempfile in workflow_data["tempfiles"]:
            try:
               if os.path.exists(tempfile):
                  os.remove(tempfile)
            except Exception:
               pass
      except Exception as e:
         pass


def sub_worker(thread_loop, threadtimes: dict):
   asyncio.set_event_loop(thread_loop)
   while True:
      try:
         threadtimes[threading.current_thread().ident] = time.time()
         threadLock.acquire()
         if len(func_list) == 0:
            threadLock.release()
            time.sleep(0.01)
            continue
         (task, args, kwargs) = func_list.pop()
         result = data_list.pop()
         threadLock.release()
         try:
            result = task(result, *args, **kwargs)
            if result["wid"] < 0:
               threadLock.acquire()
               i = 0
               while i < len(subworkflows):
                  [mainworkflow, mainnode_id, zll, subhandle, state] = subworkflows[i]
                  if result["wid"] == subhandle:
                     outfields = mainworkflow.get_node_outfields(mainnode_id)
                     index = int(mainworkflow.get_node_field_value(mainnode_id, "index"))
                     subworkflow = Workflow(result)
                     subnode_id = args[0]
                     fields = subworkflow.get_node_fields(subnode_id)
                     for field in fields:
                        outfield = subnode_id + "." + field
                        if outfield in outfields:
                           if index > 0:
                              if index == 1:
                                 outfieldvalue = []
                                 outfieldvalue.append(mainworkflow.get_node_field_value(mainnode_id, outfield))
                                 outfieldvalue.append(subworkflow.get_node_field_value(subnode_id, field))
                                 mainworkflow.update_node_field_value(mainnode_id, outfield, outfieldvalue)
                              else:
                                 outfieldvalue = mainworkflow.get_node_field_value(mainnode_id, outfield)
                                 if isinstance(outfieldvalue, list):
                                    outfieldvalue.append(subworkflow.get_node_field_value(subnode_id, field))
                                    mainworkflow.update_node_field_value(mainnode_id, outfield, outfieldvalue)
                           else:
                              mainworkflow.update_node_field_value(mainnode_id, outfield, subworkflow.get_node_field_value(subnode_id, field))
                     break
                  i += 1
               threadLock.release()
         except Exception:
            pass
         finally:
            threadLock.acquire()
            tPaused = False
            i = 0
            while i < len(pauseworkflows):
               [workflow, node_id, task_name, pausetime] = pauseworkflows[i]
               if result["wid"] == workflow.data["wid"]:
                  if node_id == args[0]:
                     result["nodesrun"].remove(
                        {
                           "node_id": node_id,
                           "task_name": task_name,
                        }
                     )
                     tPaused = True
                     break
               i += 1
            i = 0
            while i < len(subworkflows):
               [mainworkflow, mainnode_id, zll, subhandle, state] = subworkflows[i]
               if result["wid"] == mainworkflow.data["wid"]:
                  if mainnode_id == args[0]:
                     result["nodesrun"].remove(
                        {
                           "node_id": mainnode_id,
                           "task_name": mainworkflow.get_node(mainnode_id).task_name,
                        }
                     )
                     tPaused = True
                     break
               i += 1
            if not tPaused:
               result["nodesdone"].append(args[0])
            threadLock.release()
      except Exception:
         pass

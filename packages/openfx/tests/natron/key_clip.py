import os
import sys

import NatronEngine

clip = os.environ["KM_NATRON_CLIP"]
out = os.environ["KM_NATRON_OUT"]
mode = int(os.environ.get("KM_NATRON_OUTPUT", "0"))
project = os.environ.get("KM_NATRON_PROJECT", "")
press = os.environ.get("KM_NATRON_PRESS", "1") == "1"
load = os.environ.get("KM_NATRON_LOAD", "")
app = app1

if load:
    app.loadProject(load)
    km = app.getNode("Keymaster1")
    writer = app.getNode("Write1")
    writer.getParam("filename").setValue(out)
else:
    reader = app.createNode("fr.inria.built-in.Read")
    reader.getParam("filename").setValue(clip)
    frames = int(os.environ.get("KM_NATRON_FRAMES", "5"))
    original = reader.getParam("originalFrameRange")
    original.setValue(1, 0)
    original.setValue(frames, 1)
    reader.getParam("firstFrame").setValue(1)
    reader.getParam("lastFrame").setValue(frames)
    km = app.createNode("io.github.yoseptf.keymaster")
    if km is None:
        print("KM_RESULT plugin-not-found")
        sys.exit(2)
    km.connectInput(0, reader)
    writer = app.createNode("fr.inria.built-in.Write")
    writer.connectInput(0, km)
    writer.getParam("filename").setValue(out)

print("KM_LABEL " + km.getParam("keyClip").getLabel())
print("KM_PARAMS " + " ".join(p.getScriptName() for p in km.getParams()))
km.getParam("output").setValue(mode)
if press:
    km.getParam("keyClip").trigger()
print("KM_CACHE " + km.getParam("cacheDir").getValue())
print("KM_TOKEN " + km.getParam("keyToken").getValue())
reader = km.getInput(0)
app.render(writer, int(reader.getParam("firstFrame").getValue()), int(reader.getParam("lastFrame").getValue()))
if project:
    app.saveProjectAs(project)
print("KM_RESULT rendered")
sys.stdout.flush()
os._exit(0)

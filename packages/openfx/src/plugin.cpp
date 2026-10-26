#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstring>
#include <list>
#include <memory>
#include <mutex>
#include <string>
#include <system_error>
#include <vector>

#include "ofxCore.h"
#include "ofxImageEffect.h"
#include "ofxMessage.h"
#include "ofxParam.h"
#include "ofxProgress.h"
#include "ofxProperty.h"

#include "cache.hpp"
#include "events.hpp"
#include "frames.hpp"
#include "i18n.hpp"
#include "paths.hpp"
#include "process.hpp"
#include "settings.hpp"

#ifndef KM_VERSION_MAJOR
#define KM_VERSION_MAJOR 0
#endif
#ifndef KM_VERSION_MINOR
#define KM_VERSION_MINOR 0
#endif
#ifndef KM_VERSION_PATCH
#define KM_VERSION_PATCH 0
#endif
#ifndef KM_VERSION_STRING
#define KM_VERSION_STRING "0.0.0"
#endif

using namespace km;

namespace {

const char* kPluginId = "io.github.yoseptf.keymaster";
const char* kParamOutput = "output";
const char* kParamColor = "clipEncoding";
const char* kParamHintQuality = "hintQuality";
const char* kParamDespill = "despill";
const char* kParamKey = "keyClip";
const char* kParamClear = "clearKey";
const char* kParamCacheDir = "cacheDir";
const char* kParamToken = "keyToken";

enum OutputMode { OutputCutout = 0, OutputAlpha = 1, OutputForeground = 2, OutputSource = 3 };

OfxHost* gHost = nullptr;
OfxPropertySuiteV1* gProp = nullptr;
OfxImageEffectSuiteV1* gEffect = nullptr;
OfxParameterSuiteV1* gParam = nullptr;
OfxMessageSuiteV1* gMessage = nullptr;
OfxMessageSuiteV2* gMessage2 = nullptr;
OfxProgressSuiteV1* gProgress = nullptr;
std::string gHostName;

struct Instance {
    OfxImageEffectHandle effect = nullptr;
    OfxImageClipHandle source = nullptr;
    OfxImageClipHandle output = nullptr;
    OfxParamHandle outputMode = nullptr;
    OfxParamHandle color = nullptr;
    OfxParamHandle hintQuality = nullptr;
    OfxParamHandle despill = nullptr;
    OfxParamHandle cacheDir = nullptr;
    OfxParamHandle token = nullptr;
    std::mutex mutex;
    std::string loadedDir;
    std::string loadedToken;
    bool manifestLoaded = false;
    Manifest manifest;
    std::list<std::pair<std::string, std::shared_ptr<Image>>> frames;
    int shownState = -1;
    bool busy = false;
};

void setLabel(OfxPropertySetHandle props, const std::string& text) {
    gProp->propSetString(props, kOfxPropLabel, 0, text.c_str());
    gProp->propSetString(props, kOfxPropShortLabel, 0, text.c_str());
    gProp->propSetString(props, kOfxPropLongLabel, 0, text.c_str());
}

void setHint(OfxPropertySetHandle props, const std::string& text) {
    gProp->propSetString(props, kOfxParamPropHint, 0, text.c_str());
}

void setLabels(OfxPropertySetHandle props, const std::vector<std::string>& options) {
    for (size_t i = 0; i < options.size(); ++i) {
        gProp->propSetString(props, kOfxParamPropChoiceOption, (int)i, options[i].c_str());
    }
}

std::string lowerText(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) { return (char)std::tolower(c); });
    return text;
}

bool hostIsLinear() {
    std::string name = lowerText(gHostName);
    return name.find("nuke") != std::string::npos || name.find("natron") != std::string::npos;
}

Instance* getInstance(OfxImageEffectHandle effect) {
    OfxPropertySetHandle props = nullptr;
    if (gEffect->getPropertySet(effect, &props) != kOfxStatOK) return nullptr;
    void* data = nullptr;
    gProp->propGetPointer(props, kOfxPropInstanceData, 0, &data);
    return static_cast<Instance*>(data);
}

std::string paramString(OfxParamHandle param) {
    char* value = nullptr;
    if (!param || gParam->paramGetValue(param, &value) != kOfxStatOK || !value) return std::string();
    return std::string(value);
}

double paramDouble(OfxParamHandle param) {
    double value = 0.0;
    if (param) gParam->paramGetValue(param, &value);
    return value;
}

int paramInt(OfxParamHandle param) {
    int value = 0;
    if (param) gParam->paramGetValue(param, &value);
    return value;
}

const char* kFormat = "%s";

void sendMessage(Instance* inst, const char* type, const std::string& text) {
    if (gMessage) gMessage->message(inst->effect, type, nullptr, kFormat, text.c_str());
}

bool sourceRange(Instance* inst, int& first, int& last) {
    int connected = 0;
    OfxPropertySetHandle props = nullptr;
    if (gEffect->clipGetPropertySet(inst->source, &props) != kOfxStatOK) return false;
    gProp->propGetInt(props, kOfxImageClipPropConnected, 0, &connected);
    if (!connected) return false;
    double range[2] = {0.0, -1.0};
    gProp->propGetDoubleN(props, kOfxImageEffectPropFrameRange, 2, range);
    first = (int)std::ceil(range[0] - 1e-6);
    last = (int)std::floor(range[1] + 1e-6);
    return last >= first;
}

KeyRequest currentRequest(Instance* inst) {
    KeyRequest request;
    request.token = paramString(inst->token);
    if (!sourceRange(inst, request.first, request.last)) {
        request.first = 0;
        request.last = -1;
    }
    request.hintQuality = paramDouble(inst->hintQuality);
    request.despill = paramDouble(inst->despill);
    return request;
}

CacheState computeState(Instance* inst) {
    std::string dir = paramString(inst->cacheDir);
    KeyRequest request = currentRequest(inst);
    std::lock_guard<std::mutex> lock(inst->mutex);
    if (dir != inst->loadedDir || request.token != inst->loadedToken) {
        inst->loadedDir = dir;
        inst->loadedToken = request.token;
        inst->manifestLoaded = !dir.empty() && readManifest(u8path(dir), inst->manifest);
        inst->frames.clear();
    }
    return evaluateCache(dir, request.token, inst->manifestLoaded, inst->manifest, request);
}

void forgetManifest(Instance* inst) {
    std::lock_guard<std::mutex> lock(inst->mutex);
    inst->loadedDir.clear();
    inst->loadedToken.clear();
    inst->manifestLoaded = false;
    inst->frames.clear();
}

void refreshStatus(Instance* inst) {
    if (!gMessage2) return;
    CacheState state = computeState(inst);
    int code = (int)state;
    if (code == inst->shownState) return;
    inst->shownState = code;
    std::string text;
    const char* type = kOfxMessageWarning;
    switch (state) {
    case CacheState::NotKeyed:
        text = tr("openfx.status.not_keyed");
        type = kOfxMessageMessage;
        break;
    case CacheState::Missing:
        text = tr("openfx.status.missing");
        break;
    case CacheState::Stale:
        text = tr("openfx.status.stale");
        break;
    case CacheState::Ready:
        gMessage2->clearPersistentMessage(inst->effect);
        return;
    }
    gMessage2->setPersistentMessage(inst->effect, type, nullptr, kFormat, text.c_str());
}

struct ImageView {
    OfxPropertySetHandle handle = nullptr;
    char* data = nullptr;
    OfxRectI bounds{0, 0, 0, 0};
    int rowBytes = 0;
    int depth = 0;
    int components = 0;

    bool load(OfxPropertySetHandle image) {
        handle = image;
        if (!image) return false;
        void* ptr = nullptr;
        gProp->propGetPointer(image, kOfxImagePropData, 0, &ptr);
        data = static_cast<char*>(ptr);
        gProp->propGetIntN(image, kOfxImagePropBounds, 4, &bounds.x1);
        gProp->propGetInt(image, kOfxImagePropRowBytes, 0, &rowBytes);
        char* value = nullptr;
        gProp->propGetString(image, kOfxImageEffectPropPixelDepth, 0, &value);
        std::string depthName = value ? value : "";
        depth = depthName == kOfxBitDepthFloat ? 4 : depthName == kOfxBitDepthShort ? 2 : depthName == kOfxBitDepthByte ? 1 : 0;
        gProp->propGetString(image, kOfxImageEffectPropComponents, 0, &value);
        std::string comps = value ? value : "";
        components = comps == kOfxImageComponentRGBA ? 4 : comps == kOfxImageComponentRGB ? 3 : comps == kOfxImageComponentAlpha ? 1 : 0;
        return data != nullptr && depth != 0 && components != 0;
    }

    bool contains(int x, int y) const {
        return x >= bounds.x1 && x < bounds.x2 && y >= bounds.y1 && y < bounds.y2;
    }

    void read(int x, int y, float out[4]) const {
        out[0] = out[1] = out[2] = out[3] = 0.0f;
        if (!data || !contains(x, y)) return;
        const char* row = data + (ptrdiff_t)(y - bounds.y1) * rowBytes;
        size_t offset = (size_t)(x - bounds.x1) * components;
        float v[4] = {0.0f, 0.0f, 0.0f, 1.0f};
        for (int c = 0; c < components; ++c) {
            if (depth == 4) v[c] = reinterpret_cast<const float*>(row)[offset + c];
            else if (depth == 2) v[c] = reinterpret_cast<const unsigned short*>(row)[offset + c] / 65535.0f;
            else v[c] = reinterpret_cast<const unsigned char*>(row)[offset + c] / 255.0f;
        }
        if (components == 1) {
            out[3] = v[0];
        } else {
            out[0] = v[0];
            out[1] = v[1];
            out[2] = v[2];
            out[3] = components == 4 ? v[3] : 1.0f;
        }
    }

    float* pixel(int x, int y) const {
        char* row = data + (ptrdiff_t)(y - bounds.y1) * rowBytes;
        return reinterpret_cast<float*>(row) + (size_t)(x - bounds.x1) * 4;
    }
};

std::shared_ptr<Image> cachedFrame(Instance* inst, const fs::path& path) {
    std::string key = u8string(path);
    {
        std::lock_guard<std::mutex> lock(inst->mutex);
        for (auto it = inst->frames.begin(); it != inst->frames.end(); ++it) {
            if (it->first == key) {
                inst->frames.splice(inst->frames.begin(), inst->frames, it);
                return inst->frames.front().second;
            }
        }
    }
    auto image = std::make_shared<Image>();
    if (!readImage(path, *image, nullptr) || image->width <= 0 || image->height <= 0) return nullptr;
    std::lock_guard<std::mutex> lock(inst->mutex);
    inst->frames.emplace_front(key, image);
    while (inst->frames.size() > 4) inst->frames.pop_back();
    return image;
}

const char* kindForMode(int mode) {
    switch (mode) {
    case OutputCutout: return "cutout";
    case OutputAlpha: return "alpha";
    case OutputForeground: return "fg";
    default: return "";
    }
}

std::shared_ptr<Image> frameForRender(Instance* inst, int mode, double time) {
    if (mode == OutputSource || computeState(inst) != CacheState::Ready) return nullptr;
    Manifest manifest;
    {
        std::lock_guard<std::mutex> lock(inst->mutex);
        manifest = inst->manifest;
    }
    auto it = manifest.outputs.find(kindForMode(mode));
    if (it == manifest.outputs.end()) return nullptr;
    int index = (int)std::lround(time) - manifest.first;
    if (index < 0 || (it->second.frames > 0 && index >= it->second.frames)) return nullptr;
    return cachedFrame(inst, outputFramePath(u8path(paramString(inst->cacheDir)), it->second, index));
}

OfxStatus actionLoad() {
    if (!gHost) return kOfxStatErrMissingHostFeature;
    gProp = (OfxPropertySuiteV1*)gHost->fetchSuite(gHost->host, kOfxPropertySuite, 1);
    gEffect = (OfxImageEffectSuiteV1*)gHost->fetchSuite(gHost->host, kOfxImageEffectSuite, 1);
    gParam = (OfxParameterSuiteV1*)gHost->fetchSuite(gHost->host, kOfxParameterSuite, 1);
    gMessage = (OfxMessageSuiteV1*)gHost->fetchSuite(gHost->host, kOfxMessageSuite, 1);
    gMessage2 = (OfxMessageSuiteV2*)gHost->fetchSuite(gHost->host, kOfxMessageSuite, 2);
    gProgress = (OfxProgressSuiteV1*)gHost->fetchSuite(gHost->host, kOfxProgressSuite, 1);
    if (!gProp || !gEffect || !gParam) return kOfxStatErrMissingHostFeature;
    char* name = nullptr;
    if (gProp->propGetString(gHost->host, kOfxPropName, 0, &name) == kOfxStatOK && name) gHostName = name;
    initTranslator();
    return kOfxStatOK;
}

OfxStatus actionDescribe(OfxImageEffectHandle effect) {
    initTranslator();
    OfxPropertySetHandle props = nullptr;
    gEffect->getPropertySet(effect, &props);
    setLabel(props, tr("openfx.plugin.label"));
    gProp->propSetString(props, kOfxImageEffectPluginPropGrouping, 0, tr("openfx.plugin.group").c_str());
    gProp->propSetString(props, kOfxPropPluginDescription, 0, tr("openfx.plugin.description").c_str());
    int version[3] = {KM_VERSION_MAJOR, KM_VERSION_MINOR, KM_VERSION_PATCH};
    gProp->propSetIntN(props, kOfxPropVersion, 3, version);
    gProp->propSetString(props, kOfxPropVersionLabel, 0, KM_VERSION_STRING);
    gProp->propSetString(props, kOfxImageEffectPropSupportedContexts, 0, kOfxImageEffectContextFilter);
    gProp->propSetString(props, kOfxImageEffectPropSupportedContexts, 1, kOfxImageEffectContextGeneral);
    gProp->propSetString(props, kOfxImageEffectPropSupportedPixelDepths, 0, kOfxBitDepthFloat);
    gProp->propSetInt(props, kOfxImageEffectPluginPropSingleInstance, 0, 0);
    gProp->propSetString(props, kOfxImageEffectPluginRenderThreadSafety, 0, kOfxImageEffectRenderInstanceSafe);
    gProp->propSetInt(props, kOfxImageEffectPluginPropHostFrameThreading, 0, 0);
    gProp->propSetInt(props, kOfxImageEffectPropSupportsMultiResolution, 0, 0);
    gProp->propSetInt(props, kOfxImageEffectPropSupportsTiles, 0, 1);
    gProp->propSetInt(props, kOfxImageEffectPropTemporalClipAccess, 0, 1);
    gProp->propSetInt(props, kOfxImageEffectPropSupportsMultipleClipDepths, 0, 0);
    gProp->propSetInt(props, kOfxImageEffectPluginPropFieldRenderTwiceAlways, 0, 0);
    gProp->propSetString(props, kOfxImageEffectPropClipPreferencesSlaveParam, 0, kParamOutput);
    gProp->propSetString(props, kOfxImageEffectPropClipPreferencesSlaveParam, 1, kParamToken);
    return kOfxStatOK;
}

void defineParam(OfxParamSetHandle params, const char* type, const char* name, OfxPropertySetHandle* props) {
    gParam->paramDefine(params, type, name, props);
    gProp->propSetInt(*props, kOfxParamPropAnimates, 0, 0);
}

void defineDouble(OfxParamSetHandle params, const char* name, double value, const std::string& label, const std::string& hint) {
    OfxPropertySetHandle props = nullptr;
    defineParam(params, kOfxParamTypeDouble, name, &props);
    setLabel(props, label);
    setHint(props, hint);
    gProp->propSetDouble(props, kOfxParamPropDefault, 0, value);
    gProp->propSetDouble(props, kOfxParamPropMin, 0, 0.0);
    gProp->propSetDouble(props, kOfxParamPropMax, 0, 1.0);
    gProp->propSetDouble(props, kOfxParamPropDisplayMin, 0, 0.0);
    gProp->propSetDouble(props, kOfxParamPropDisplayMax, 0, 1.0);
    gProp->propSetDouble(props, kOfxParamPropIncrement, 0, 0.01);
    gProp->propSetInt(props, kOfxParamPropDigits, 0, 2);
    gProp->propSetString(props, kOfxParamPropDoubleType, 0, kOfxParamDoubleTypePlain);
}

void defineButton(OfxParamSetHandle params, const char* name, const std::string& label, const std::string& hint) {
    OfxPropertySetHandle props = nullptr;
    gParam->paramDefine(params, kOfxParamTypePushButton, name, &props);
    setLabel(props, label);
    setHint(props, hint);
}

void defineSecret(OfxParamSetHandle params, const char* name, const std::string& label) {
    OfxPropertySetHandle props = nullptr;
    defineParam(params, kOfxParamTypeString, name, &props);
    setLabel(props, label);
    gProp->propSetString(props, kOfxParamPropDefault, 0, "");
    gProp->propSetInt(props, kOfxParamPropSecret, 0, 1);
    gProp->propSetInt(props, kOfxParamPropPersistant, 0, 1);
    gProp->propSetInt(props, kOfxParamPropEvaluateOnChange, 0, 1);
    gProp->propSetString(props, kOfxParamPropStringMode, 0, kOfxParamStringIsSingleLine);
}

OfxStatus actionDescribeInContext(OfxImageEffectHandle effect) {
    OfxPropertySetHandle props = nullptr;
    gEffect->clipDefine(effect, kOfxImageEffectSimpleSourceClipName, &props);
    gProp->propSetString(props, kOfxImageEffectPropSupportedComponents, 0, kOfxImageComponentRGBA);
    gProp->propSetString(props, kOfxImageEffectPropSupportedComponents, 1, kOfxImageComponentRGB);
    gProp->propSetInt(props, kOfxImageEffectPropTemporalClipAccess, 0, 1);
    gProp->propSetInt(props, kOfxImageEffectPropSupportsTiles, 0, 1);
    gProp->propSetInt(props, kOfxImageClipPropOptional, 0, 0);
    gEffect->clipDefine(effect, kOfxImageEffectOutputClipName, &props);
    gProp->propSetString(props, kOfxImageEffectPropSupportedComponents, 0, kOfxImageComponentRGBA);
    gProp->propSetInt(props, kOfxImageEffectPropSupportsTiles, 0, 1);

    OfxParamSetHandle params = nullptr;
    gEffect->getParamSet(effect, &params);

    defineButton(params, kParamKey, tr("openfx.param.key.label"), tr("openfx.param.key.hint"));

    defineParam(params, kOfxParamTypeChoice, kParamOutput, &props);
    setLabel(props, tr("openfx.param.output.label"));
    setHint(props, tr("openfx.param.output.hint"));
    setLabels(props, {tr("openfx.param.output.cutout"), tr("openfx.param.output.alpha"),
                      tr("openfx.param.output.fg"), tr("openfx.param.output.source")});
    gProp->propSetInt(props, kOfxParamPropDefault, 0, OutputCutout);

    defineDouble(params, kParamHintQuality, 0.95, tr("openfx.param.hint_quality.label"), tr("openfx.param.hint_quality.hint"));
    defineDouble(params, kParamDespill, 0.5, tr("openfx.param.despill.label"), tr("openfx.param.despill.hint"));

    defineParam(params, kOfxParamTypeChoice, kParamColor, &props);
    setLabel(props, tr("openfx.param.encoding.label"));
    setHint(props, tr("openfx.param.encoding.hint"));
    setLabels(props, {tr("openfx.param.encoding.gamma"), tr("openfx.param.encoding.linear")});
    gProp->propSetInt(props, kOfxParamPropDefault, 0, hostIsLinear() ? 1 : 0);

    defineButton(params, kParamClear, tr("openfx.param.clear.label"), tr("openfx.param.clear.hint"));
    defineSecret(params, kParamCacheDir, tr("openfx.param.cache_dir.label"));
    defineSecret(params, kParamToken, tr("openfx.param.key_token.label"));
    return kOfxStatOK;
}

OfxStatus actionCreateInstance(OfxImageEffectHandle effect) {
    auto* inst = new Instance();
    inst->effect = effect;
    gEffect->clipGetHandle(effect, kOfxImageEffectSimpleSourceClipName, &inst->source, nullptr);
    gEffect->clipGetHandle(effect, kOfxImageEffectOutputClipName, &inst->output, nullptr);
    OfxParamSetHandle params = nullptr;
    gEffect->getParamSet(effect, &params);
    gParam->paramGetHandle(params, kParamOutput, &inst->outputMode, nullptr);
    gParam->paramGetHandle(params, kParamColor, &inst->color, nullptr);
    gParam->paramGetHandle(params, kParamHintQuality, &inst->hintQuality, nullptr);
    gParam->paramGetHandle(params, kParamDespill, &inst->despill, nullptr);
    gParam->paramGetHandle(params, kParamCacheDir, &inst->cacheDir, nullptr);
    gParam->paramGetHandle(params, kParamToken, &inst->token, nullptr);
    OfxPropertySetHandle props = nullptr;
    gEffect->getPropertySet(effect, &props);
    gProp->propSetPointer(props, kOfxPropInstanceData, 0, inst);
    refreshStatus(inst);
    return kOfxStatOK;
}

OfxStatus actionDestroyInstance(OfxImageEffectHandle effect) {
    Instance* inst = getInstance(effect);
    if (inst) {
        OfxPropertySetHandle props = nullptr;
        gEffect->getPropertySet(effect, &props);
        gProp->propSetPointer(props, kOfxPropInstanceData, 0, nullptr);
        delete inst;
    }
    return kOfxStatOK;
}

class Progress {
public:
    explicit Progress(Instance* inst) : inst_(inst) {}
    ~Progress() { end(); }

    void start(const std::string& label) {
        if (!gProgress || (active_ && label == label_)) return;
        end();
        label_ = label;
        active_ = gProgress->progressStart(inst_->effect, label.c_str()) == kOfxStatOK;
    }

    bool update(double fraction) {
        last_ = std::min(1.0, std::max(last_, fraction));
        if (!gProgress || !active_) return true;
        return gProgress->progressUpdate(inst_->effect, last_) != kOfxStatReplyNo;
    }

    bool poll() { return update(last_); }

    void end() {
        if (gProgress && active_) gProgress->progressEnd(inst_->effect);
        active_ = false;
    }

private:
    Instance* inst_;
    bool active_ = false;
    double last_ = 0.0;
    std::string label_;
};

const double kExportShare = 0.2;

bool exportFrames(Instance* inst, const fs::path& dir, int first, int last, bool linear, Progress& progress,
                  int& width, int& height, std::string& error, bool& cancelled) {
    std::error_code ec;
    fs::create_directories(inputDir(dir), ec);
    int count = last - first + 1;
    progress.start(tr("openfx.progress.reading"));
    for (int i = 0; i < count; ++i) {
        if (!progress.update(kExportShare * i / count)) {
            cancelled = true;
            return false;
        }
        OfxPropertySetHandle handle = nullptr;
        if (gEffect->clipGetImage(inst->source, (double)(first + i), nullptr, &handle) != kOfxStatOK || !handle) {
            error = tr("openfx.error.fetch_failed", {{"frame", first + i}});
            return false;
        }
        ImageView view;
        bool ok = view.load(handle);
        int w = view.bounds.x2 - view.bounds.x1;
        int h = view.bounds.y2 - view.bounds.y1;
        if (!ok || w <= 0 || h <= 0) {
            gEffect->clipReleaseImage(handle);
            error = tr("openfx.error.fetch_failed", {{"frame", first + i}});
            return false;
        }
        std::vector<float> rgb((size_t)w * h * 3);
        float px[4];
        for (int r = 0; r < h; ++r) {
            int y = view.bounds.y2 - 1 - r;
            for (int x = 0; x < w; ++x) {
                view.read(view.bounds.x1 + x, y, px);
                float* o = &rgb[((size_t)r * w + x) * 3];
                for (int c = 0; c < 3; ++c) o[c] = linear ? linearToSrgb(px[c]) : px[c];
            }
        }
        gEffect->clipReleaseImage(handle);
        if (i == 0) {
            width = w;
            height = h;
        }
        std::string writeError;
        if (!writeExrRgb(inputFramePath(dir, i), w, h, rgb, &writeError)) {
            error = tr("openfx.error.write_failed", {{"detail", writeError}});
            return false;
        }
    }
    return true;
}

void runKey(Instance* inst) {
    if (inst->busy) return;
    inst->busy = true;
    struct Reset {
        Instance* inst;
        ~Reset() { inst->busy = false; }
    } reset{inst};

    EnvFn env = processEnv();
    Settings settings = loadSettings(settingsPath(env));
    CoreLocation core = resolveCore(env, settings);
    std::error_code ec;
    if (core.python.empty() || core.core.empty()) {
        std::string message = tr("openfx.error.no_core");
        sendMessage(inst, kOfxMessageError, message);
        return;
    }
    if (!fs::exists(u8path(core.python), ec)) {
        std::string message = tr("openfx.error.no_python", {{"path", core.python}});
        sendMessage(inst, kOfxMessageError, message);
        return;
    }
    if (!fs::is_directory(u8path(core.core), ec)) {
        std::string message = tr("openfx.error.core_missing", {{"path", core.core}});
        sendMessage(inst, kOfxMessageError, message);
        return;
    }
    int first = 0, last = -1;
    if (!sourceRange(inst, first, last)) {
        std::string message = tr("openfx.error.no_source");
        sendMessage(inst, kOfxMessageError, message);
        return;
    }

    std::string dirText = paramString(inst->cacheDir);
    fs::path dir = dirText.empty() ? fs::path() : u8path(dirText);
    if (dir.empty() || u8string(dir.filename()).rfind("km-", 0) != 0) {
        dir = cacheRoot(env) / newCacheName();
    }
    clearCacheDir(dir);
    fs::create_directories(dir, ec);
    if (ec) {
        std::string message = tr("openfx.error.write_failed", {{"detail", u8string(dir)}});
        sendMessage(inst, kOfxMessageError, message);
        return;
    }
    forgetManifest(inst);
    gParam->paramSetValue(inst->cacheDir, u8string(dir).c_str());

    double hintQuality = paramDouble(inst->hintQuality);
    double despill = paramDouble(inst->despill);
    bool linear = paramInt(inst->color) == 1;

    Progress progress(inst);
    int width = 0, height = 0;
    std::string error;
    bool cancelled = false;
    if (!exportFrames(inst, dir, first, last, linear, progress, width, height, error, cancelled)) {
        progress.end();
        fs::remove_all(inputDir(dir), ec);
        if (!cancelled) sendMessage(inst, kOfxMessageError, error);
        refreshStatus(inst);
        return;
    }

    char number[64];
    std::vector<std::string> argv = {core.python, "-m", "keymaster", "key",
                                     "--input", u8string(inputDir(dir)),
                                     "--output-dir", u8string(outputDir(dir)),
                                     "--format", "exr", "--outputs", "alpha", "fg", "cutout"};
    std::snprintf(number, sizeof(number), "%.4f", hintQuality);
    argv.insert(argv.end(), {"--hint-quality", number});
    std::snprintf(number, sizeof(number), "%.4f", despill);
    argv.insert(argv.end(), {"--despill", number});
    argv.insert(argv.end(), {"--frames", std::to_string(last - first + 1), "--json"});

    Event event;
    bool haveError = false;
    bool done = false;
    Event errorEvent;
    std::vector<OutputInfo> outputs;
    std::string fallbackLabel = tr("openfx.progress.keying");
    progress.start(fallbackLabel);
    bool userCancelled = false;
    RunResult result = runProcess(
        argv, core.core, logPath(dir),
        [&](const std::string& line) {
            if (!parseEvent(line, event)) return;
            switch (event.kind) {
            case EventKind::Progress:
                progress.start(trCore(event.messageKey, nlohmann::json::object(), fallbackLabel));
                if (!progress.update(kExportShare + (1.0 - kExportShare) * event.fraction)) userCancelled = true;
                break;
            case EventKind::Output:
                outputs.push_back(event.output);
                break;
            case EventKind::Done:
                done = true;
                if (!event.outputs.empty()) outputs = event.outputs;
                break;
            case EventKind::Error:
                haveError = true;
                errorEvent = event;
                break;
            default:
                break;
            }
        },
        [&]() {
            if (!userCancelled && !progress.poll()) userCancelled = true;
            return userCancelled;
        });
    progress.end();
    fs::remove_all(inputDir(dir), ec);

    if (result.cancelled) {
        refreshStatus(inst);
        return;
    }
    std::string logNote = tr("openfx.error.see_log", {{"path", u8string(logPath(dir))}});
    if (!result.started) {
        std::string message = tr("openfx.error.start_failed", {{"detail", result.error}});
        sendMessage(inst, kOfxMessageError, message);
        refreshStatus(inst);
        return;
    }
    if (result.exitCode != 0 || haveError || !done) {
        std::string text;
        if (haveError) {
            std::string fallback = tr("openfx.error.core_failed", {{"detail", errorEvent.detail.empty() ? errorEvent.messageKey : errorEvent.detail}});
            text = trCore(errorEvent.messageKey, errorEvent.params, fallback);
        } else {
            text = tr("openfx.error.core_failed", {{"detail", std::to_string(result.exitCode)}});
        }
        std::string message = text + "\n" + logNote;
        sendMessage(inst, kOfxMessageError, message);
        refreshStatus(inst);
        return;
    }

    Manifest manifest;
    manifest.token = newToken();
    manifest.first = first;
    manifest.last = last;
    manifest.width = width;
    manifest.height = height;
    manifest.hintQuality = hintQuality;
    manifest.despill = despill;
    for (const auto& output : outputs) {
        if (output.type == "image_sequence" && !output.pattern.empty()) manifest.outputs[output.kind] = output;
    }
    if (manifest.outputs.empty()) {
        std::string message = tr("openfx.error.no_outputs") + "\n" + logNote;
        sendMessage(inst, kOfxMessageError, message);
        refreshStatus(inst);
        return;
    }
    if (!writeManifest(dir, manifest)) {
        std::string message = tr("openfx.error.write_failed", {{"detail", u8string(manifestPath(dir))}});
        sendMessage(inst, kOfxMessageError, message);
        refreshStatus(inst);
        return;
    }
    forgetManifest(inst);
    gParam->paramSetValue(inst->token, manifest.token.c_str());
    refreshStatus(inst);
}

void clearKey(Instance* inst) {
    if (inst->busy) return;
    std::string dir = paramString(inst->cacheDir);
    if (!dir.empty()) clearCacheDir(u8path(dir));
    forgetManifest(inst);
    gParam->paramSetValue(inst->token, "");
    gParam->paramSetValue(inst->cacheDir, "");
    refreshStatus(inst);
}

OfxStatus actionInstanceChanged(OfxImageEffectHandle effect, OfxPropertySetHandle args) {
    Instance* inst = getInstance(effect);
    if (!inst) return kOfxStatFailed;
    char* type = nullptr;
    char* name = nullptr;
    gProp->propGetString(args, kOfxPropType, 0, &type);
    gProp->propGetString(args, kOfxPropName, 0, &name);
    std::string typeText = type ? type : "";
    std::string nameText = name ? name : "";
    if (typeText == kOfxTypeParameter && nameText == kParamKey) {
        runKey(inst);
    } else if (typeText == kOfxTypeParameter && nameText == kParamClear) {
        clearKey(inst);
    } else {
        refreshStatus(inst);
    }
    return kOfxStatOK;
}

OfxStatus actionIsIdentity(OfxImageEffectHandle effect, OfxPropertySetHandle outArgs) {
    Instance* inst = getInstance(effect);
    if (!inst) return kOfxStatReplyDefault;
    int mode = paramInt(inst->outputMode);
    if (mode == OutputSource || computeState(inst) != CacheState::Ready) {
        gProp->propSetString(outArgs, kOfxPropName, 0, kOfxImageEffectSimpleSourceClipName);
        return kOfxStatOK;
    }
    return kOfxStatReplyDefault;
}

OfxStatus actionClipPreferences(OfxImageEffectHandle effect, OfxPropertySetHandle outArgs) {
    Instance* inst = getInstance(effect);
    if (!inst) return kOfxStatReplyDefault;
    gProp->propSetString(outArgs, "OfxImageClipPropComponents_Output", 0, kOfxImageComponentRGBA);
    gProp->propSetString(outArgs, "OfxImageClipPropComponents_Source", 0, kOfxImageComponentRGBA);
    int mode = paramInt(inst->outputMode);
    bool ready = mode != OutputSource && computeState(inst) == CacheState::Ready;
    if (ready) {
        gProp->propSetString(outArgs, kOfxImageEffectPropPreMultiplication, 0,
                             mode == OutputForeground ? kOfxImageOpaque : kOfxImagePreMultiplied);
    } else {
        OfxPropertySetHandle props = nullptr;
        char* premult = nullptr;
        if (gEffect->clipGetPropertySet(inst->source, &props) == kOfxStatOK &&
            gProp->propGetString(props, kOfxImageEffectPropPreMultiplication, 0, &premult) == kOfxStatOK && premult) {
            gProp->propSetString(outArgs, kOfxImageEffectPropPreMultiplication, 0, premult);
        }
    }
    return kOfxStatOK;
}

OfxStatus actionRender(OfxImageEffectHandle effect, OfxPropertySetHandle inArgs) {
    Instance* inst = getInstance(effect);
    if (!inst) return kOfxStatFailed;
    double time = 0.0;
    OfxRectI window{0, 0, 0, 0};
    double scale[2] = {1.0, 1.0};
    gProp->propGetDouble(inArgs, kOfxPropTime, 0, &time);
    gProp->propGetIntN(inArgs, kOfxImageEffectPropRenderWindow, 4, &window.x1);
    gProp->propGetDoubleN(inArgs, kOfxImageEffectPropRenderScale, 2, scale);

    OfxPropertySetHandle outHandle = nullptr;
    if (gEffect->clipGetImage(inst->output, time, nullptr, &outHandle) != kOfxStatOK || !outHandle) return kOfxStatFailed;
    ImageView dst;
    if (!dst.load(outHandle) || dst.depth != 4 || dst.components != 4) {
        gEffect->clipReleaseImage(outHandle);
        return kOfxStatErrImageFormat;
    }
    OfxPropertySetHandle srcHandle = nullptr;
    gEffect->clipGetImage(inst->source, time, nullptr, &srcHandle);
    ImageView src;
    src.load(srcHandle);

    int mode = paramInt(inst->outputMode);
    bool linear = paramInt(inst->color) == 1;
    std::shared_ptr<Image> frame = frameForRender(inst, mode, time);

    OfxRectD rod{0, 0, 0, 0};
    double par = 1.0;
    OfxPropertySetHandle srcClipProps = nullptr;
    if (frame) {
        gEffect->clipGetRegionOfDefinition(inst->source, time, &rod);
        if (gEffect->clipGetPropertySet(inst->source, &srcClipProps) == kOfxStatOK) {
            gProp->propGetDouble(srcClipProps, kOfxImagePropPixelAspectRatio, 0, &par);
        }
        if (par <= 0.0) par = 1.0;
    }
    double fx1 = rod.x1 * scale[0] / par;
    double fx2 = rod.x2 * scale[0] / par;
    double fy1 = rod.y1 * scale[1];
    double fy2 = rod.y2 * scale[1];
    if (frame && (fx2 - fx1 < 1.0 || fy2 - fy1 < 1.0)) frame.reset();

    int x1 = std::max(window.x1, dst.bounds.x1);
    int x2 = std::min(window.x2, dst.bounds.x2);
    int y1 = std::max(window.y1, dst.bounds.y1);
    int y2 = std::min(window.y2, dst.bounds.y2);
    for (int y = y1; y < y2; ++y) {
        if ((y & 31) == 0 && gEffect->abort(effect)) break;
        int row = 0;
        if (frame) {
            double v = (y + 0.5 - fy1) / (fy2 - fy1);
            row = frame->height - 1 - (int)std::floor(v * frame->height);
            row = std::min(frame->height - 1, std::max(0, row));
        }
        for (int x = x1; x < x2; ++x) {
            float* out = dst.pixel(x, y);
            if (!frame) {
                src.read(x, y, out);
                continue;
            }
            double u = (x + 0.5 - fx1) / (fx2 - fx1);
            int col = std::min(frame->width - 1, std::max(0, (int)std::floor(u * frame->width)));
            const float* p = &frame->rgba[((size_t)row * frame->width + col) * 4];
            float rgb[3] = {p[0], p[1], p[2]};
            if (mode != OutputAlpha) {
                for (float& c : rgb) {
                    if (frame->linear && !linear) c = linearToSrgb(c);
                    else if (!frame->linear && linear) c = srgbToLinear(c);
                }
            }
            if (mode == OutputCutout) {
                float a = p[3];
                out[0] = rgb[0] * a;
                out[1] = rgb[1] * a;
                out[2] = rgb[2] * a;
                out[3] = a;
            } else if (mode == OutputAlpha) {
                out[0] = out[1] = out[2] = out[3] = p[0];
            } else {
                out[0] = rgb[0];
                out[1] = rgb[1];
                out[2] = rgb[2];
                out[3] = 1.0f;
            }
        }
    }
    if (srcHandle) gEffect->clipReleaseImage(srcHandle);
    gEffect->clipReleaseImage(outHandle);
    return kOfxStatOK;
}

OfxStatus mainEntry(const char* action, const void* handle, OfxPropertySetHandle inArgs, OfxPropertySetHandle outArgs) {
    try {
        OfxImageEffectHandle effect = (OfxImageEffectHandle)handle;
        if (std::strcmp(action, kOfxActionLoad) == 0) return actionLoad();
        if (std::strcmp(action, kOfxActionUnload) == 0) return kOfxStatOK;
        if (std::strcmp(action, kOfxActionDescribe) == 0) return actionDescribe(effect);
        if (std::strcmp(action, kOfxImageEffectActionDescribeInContext) == 0) return actionDescribeInContext(effect);
        if (std::strcmp(action, kOfxActionCreateInstance) == 0) return actionCreateInstance(effect);
        if (std::strcmp(action, kOfxActionDestroyInstance) == 0) return actionDestroyInstance(effect);
        if (std::strcmp(action, kOfxActionInstanceChanged) == 0) return actionInstanceChanged(effect, inArgs);
        if (std::strcmp(action, kOfxImageEffectActionIsIdentity) == 0) return actionIsIdentity(effect, outArgs);
        if (std::strcmp(action, kOfxImageEffectActionGetClipPreferences) == 0) return actionClipPreferences(effect, outArgs);
        if (std::strcmp(action, kOfxImageEffectActionRender) == 0) return actionRender(effect, inArgs);
        if (std::strcmp(action, kOfxImageEffectActionBeginSequenceRender) == 0) {
            Instance* inst = getInstance(effect);
            if (inst) refreshStatus(inst);
            return kOfxStatOK;
        }
    } catch (const std::exception&) {
        return kOfxStatFailed;
    }
    return kOfxStatReplyDefault;
}

void setHost(OfxHost* host) {
    gHost = host;
}

OfxPlugin gPlugin = {kOfxImageEffectPluginApi, 1, kPluginId, KM_VERSION_MAJOR, KM_VERSION_MINOR, setHost, mainEntry};

}

OfxExport int OfxGetNumberOfPlugins(void) {
    return 1;
}

OfxExport OfxPlugin* OfxGetPlugin(int nth) {
    return nth == 0 ? &gPlugin : nullptr;
}

#include <cmath>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include <dlfcn.h>

#include "ofxCore.h"
#include "ofxImageEffect.h"
#include "ofxMessage.h"
#include "ofxParam.h"
#include "ofxProgress.h"
#include "ofxProperty.h"

#include "check.hpp"

namespace fs = std::filesystem;

struct Prop {
    std::vector<std::string> s;
    std::vector<double> d;
    std::vector<int> i;
    std::vector<void*> p;
};

struct PropSet {
    std::map<std::string, Prop> props;
};

struct Param {
    std::string type;
    std::string name;
    PropSet props;
    std::string s;
    double d = 0.0;
    int i = 0;
};

struct ParamSet {
    PropSet props;
    std::vector<std::unique_ptr<Param>> params;
    Param* find(const std::string& name) {
        for (auto& p : params)
            if (p->name == name) return p.get();
        return nullptr;
    }
};

struct Effect;

struct Clip {
    std::string name;
    PropSet props;
    Effect* effect = nullptr;
};

struct Effect {
    PropSet props;
    ParamSet params;
    std::map<std::string, std::unique_ptr<Clip>> clips;
};

struct HostImage {
    PropSet props;
    std::vector<float> pixels;
};

static OfxPropertySetHandle H(PropSet* p) { return reinterpret_cast<OfxPropertySetHandle>(p); }
static PropSet* P(OfxPropertySetHandle h) { return reinterpret_cast<PropSet*>(h); }

static const int W = 8;
static const int Hh = 6;
static int gFirst = 1;
static int gLast = 3;
static int gLiveImages = 0;
static std::vector<std::string> gMessages;
static std::string gPersistent;
static std::vector<std::string> gProgressLabels;
static std::vector<double> gProgress;
static Effect* gOutputImageOwner = nullptr;
static std::vector<float>* gOutputPixels = nullptr;

static Prop& prop(OfxPropertySetHandle h, const char* name) { return P(h)->props[name]; }

template <class T>
static void put(std::vector<T>& v, int index, T value) {
    if ((int)v.size() <= index) v.resize(index + 1);
    v[index] = value;
}

static OfxStatus propSetPointer(OfxPropertySetHandle h, const char* n, int i, void* v) { put(prop(h, n).p, i, v); return kOfxStatOK; }
static OfxStatus propSetString(OfxPropertySetHandle h, const char* n, int i, const char* v) { put(prop(h, n).s, i, std::string(v)); return kOfxStatOK; }
static OfxStatus propSetDouble(OfxPropertySetHandle h, const char* n, int i, double v) { put(prop(h, n).d, i, v); return kOfxStatOK; }
static OfxStatus propSetInt(OfxPropertySetHandle h, const char* n, int i, int v) { put(prop(h, n).i, i, v); return kOfxStatOK; }
static OfxStatus propSetDoubleN(OfxPropertySetHandle h, const char* n, int c, const double* v) { for (int k = 0; k < c; ++k) put(prop(h, n).d, k, v[k]); return kOfxStatOK; }
static OfxStatus propSetIntN(OfxPropertySetHandle h, const char* n, int c, const int* v) { for (int k = 0; k < c; ++k) put(prop(h, n).i, k, v[k]); return kOfxStatOK; }

static Prop* lookup(OfxPropertySetHandle h, const char* n) {
    auto it = P(h)->props.find(n);
    return it == P(h)->props.end() ? nullptr : &it->second;
}

static OfxStatus propGetPointer(OfxPropertySetHandle h, const char* n, int i, void** v) {
    Prop* p = lookup(h, n);
    if (!p || (int)p->p.size() <= i) return kOfxStatErrUnknown;
    *v = p->p[i];
    return kOfxStatOK;
}
static OfxStatus propGetString(OfxPropertySetHandle h, const char* n, int i, char** v) {
    Prop* p = lookup(h, n);
    if (!p || (int)p->s.size() <= i) return kOfxStatErrUnknown;
    *v = const_cast<char*>(p->s[i].c_str());
    return kOfxStatOK;
}
static OfxStatus propGetDouble(OfxPropertySetHandle h, const char* n, int i, double* v) {
    Prop* p = lookup(h, n);
    if (!p || (int)p->d.size() <= i) return kOfxStatErrUnknown;
    *v = p->d[i];
    return kOfxStatOK;
}
static OfxStatus propGetInt(OfxPropertySetHandle h, const char* n, int i, int* v) {
    Prop* p = lookup(h, n);
    if (!p || (int)p->i.size() <= i) return kOfxStatErrUnknown;
    *v = p->i[i];
    return kOfxStatOK;
}
static OfxStatus propGetDoubleN(OfxPropertySetHandle h, const char* n, int c, double* v) {
    for (int k = 0; k < c; ++k)
        if (propGetDouble(h, n, k, v + k) != kOfxStatOK) return kOfxStatErrUnknown;
    return kOfxStatOK;
}
static OfxStatus propGetIntN(OfxPropertySetHandle h, const char* n, int c, int* v) {
    for (int k = 0; k < c; ++k)
        if (propGetInt(h, n, k, v + k) != kOfxStatOK) return kOfxStatErrUnknown;
    return kOfxStatOK;
}

static OfxStatus getPropertySet(OfxImageEffectHandle e, OfxPropertySetHandle* out) {
    *out = H(&reinterpret_cast<Effect*>(e)->props);
    return kOfxStatOK;
}
static OfxStatus getParamSet(OfxImageEffectHandle e, OfxParamSetHandle* out) {
    *out = reinterpret_cast<OfxParamSetHandle>(&reinterpret_cast<Effect*>(e)->params);
    return kOfxStatOK;
}
static OfxStatus clipDefine(OfxImageEffectHandle e, const char* name, OfxPropertySetHandle* out) {
    auto clip = std::make_unique<Clip>();
    clip->name = name;
    clip->effect = reinterpret_cast<Effect*>(e);
    *out = H(&clip->props);
    reinterpret_cast<Effect*>(e)->clips[name] = std::move(clip);
    return kOfxStatOK;
}
static OfxStatus clipGetHandle(OfxImageEffectHandle e, const char* name, OfxImageClipHandle* clip, OfxPropertySetHandle* props) {
    auto& clips = reinterpret_cast<Effect*>(e)->clips;
    auto it = clips.find(name);
    if (it == clips.end()) return kOfxStatErrBadHandle;
    *clip = reinterpret_cast<OfxImageClipHandle>(it->second.get());
    if (props) *props = H(&it->second->props);
    return kOfxStatOK;
}
static OfxStatus clipGetPropertySet(OfxImageClipHandle c, OfxPropertySetHandle* out) {
    *out = H(&reinterpret_cast<Clip*>(c)->props);
    return kOfxStatOK;
}

static float sourceValue(int x, int y, int c, double t) {
    if (c == 3) return 1.0f;
    if (c == 1) return 0.8f;
    return 0.05f * x + 0.02f * y + 0.01f * c + 0.001f * (float)t;
}

static OfxStatus clipGetImage(OfxImageClipHandle c, OfxTime t, const OfxRectD*, OfxPropertySetHandle* out) {
    Clip* clip = reinterpret_cast<Clip*>(c);
    auto* img = new HostImage();
    img->pixels.assign((size_t)W * Hh * 4, 0.0f);
    if (clip->name == kOfxImageEffectSimpleSourceClipName) {
        for (int y = 0; y < Hh; ++y)
            for (int x = 0; x < W; ++x)
                for (int k = 0; k < 4; ++k) img->pixels[((size_t)y * W + x) * 4 + k] = sourceValue(x, y, k, t);
    } else {
        gOutputPixels = &img->pixels;
    }
    OfxPropertySetHandle h = H(&img->props);
    propSetPointer(h, kOfxImagePropData, 0, img->pixels.data());
    int bounds[4] = {0, 0, W, Hh};
    propSetIntN(h, kOfxImagePropBounds, 4, bounds);
    propSetInt(h, kOfxImagePropRowBytes, 0, W * 4 * (int)sizeof(float));
    propSetString(h, kOfxImageEffectPropPixelDepth, 0, kOfxBitDepthFloat);
    propSetString(h, kOfxImageEffectPropComponents, 0, kOfxImageComponentRGBA);
    propSetPointer(h, "stub.image", 0, img);
    ++gLiveImages;
    *out = h;
    return kOfxStatOK;
}

static std::vector<std::unique_ptr<HostImage>> gReleasedOutputs;

static OfxStatus clipReleaseImage(OfxPropertySetHandle h) {
    void* ptr = nullptr;
    propGetPointer(h, "stub.image", 0, &ptr);
    auto* img = static_cast<HostImage*>(ptr);
    --gLiveImages;
    if (gOutputPixels == &img->pixels) {
        gReleasedOutputs.emplace_back(img);
        return kOfxStatOK;
    }
    delete img;
    return kOfxStatOK;
}
static OfxStatus clipGetRegionOfDefinition(OfxImageClipHandle, OfxTime, OfxRectD* rod) {
    *rod = OfxRectD{0, 0, (double)W, (double)Hh};
    return kOfxStatOK;
}
static int effectAbort(OfxImageEffectHandle) { return 0; }

static OfxStatus paramDefine(OfxParamSetHandle s, const char* type, const char* name, OfxPropertySetHandle* out) {
    auto* set = reinterpret_cast<ParamSet*>(s);
    auto param = std::make_unique<Param>();
    param->type = type;
    param->name = name;
    *out = H(&param->props);
    set->params.push_back(std::move(param));
    return kOfxStatOK;
}
static OfxStatus paramGetHandle(OfxParamSetHandle s, const char* name, OfxParamHandle* out, OfxPropertySetHandle* props) {
    Param* p = reinterpret_cast<ParamSet*>(s)->find(name);
    if (!p) return kOfxStatErrUnknown;
    *out = reinterpret_cast<OfxParamHandle>(p);
    if (props) *props = H(&p->props);
    return kOfxStatOK;
}
static OfxStatus paramGetPropertySet(OfxParamHandle h, OfxPropertySetHandle* out) {
    *out = H(&reinterpret_cast<Param*>(h)->props);
    return kOfxStatOK;
}
static OfxStatus paramGetValue(OfxParamHandle h, ...) {
    Param* p = reinterpret_cast<Param*>(h);
    va_list ap;
    va_start(ap, h);
    if (p->type == kOfxParamTypeDouble) *va_arg(ap, double*) = p->d;
    else if (p->type == kOfxParamTypeString) *va_arg(ap, char**) = const_cast<char*>(p->s.c_str());
    else *va_arg(ap, int*) = p->i;
    va_end(ap);
    return kOfxStatOK;
}
static OfxStatus paramSetValue(OfxParamHandle h, ...) {
    Param* p = reinterpret_cast<Param*>(h);
    va_list ap;
    va_start(ap, h);
    if (p->type == kOfxParamTypeDouble) p->d = va_arg(ap, double);
    else if (p->type == kOfxParamTypeString) p->s = va_arg(ap, const char*);
    else p->i = va_arg(ap, int);
    va_end(ap);
    return kOfxStatOK;
}

static OfxStatus message(void*, const char* type, const char*, const char* format, ...) {
    char buffer[4096];
    va_list ap;
    va_start(ap, format);
    std::vsnprintf(buffer, sizeof(buffer), format, ap);
    va_end(ap);
    gMessages.push_back(std::string(type) + ": " + buffer);
    std::fprintf(stderr, "host message %s: %s\n", type, buffer);
    return kOfxStatOK;
}
static OfxStatus setPersistentMessage(void*, const char*, const char*, const char* format, ...) {
    char buffer[4096];
    va_list ap;
    va_start(ap, format);
    std::vsnprintf(buffer, sizeof(buffer), format, ap);
    va_end(ap);
    gPersistent = buffer;
    return kOfxStatOK;
}
static OfxStatus clearPersistentMessage(void*) {
    gPersistent.clear();
    return kOfxStatOK;
}
static OfxStatus progressStart(void*, const char* label) {
    gProgressLabels.push_back(label);
    return kOfxStatOK;
}
static OfxStatus progressUpdate(void*, double value) {
    gProgress.push_back(value);
    return kOfxStatOK;
}
static OfxStatus progressEnd(void*) { return kOfxStatOK; }

static PropSet gHostProps;
static OfxPropertySuiteV1 gPropSuite{};
static OfxImageEffectSuiteV1 gEffectSuite{};
static OfxParameterSuiteV1 gParamSuite{};
static OfxMessageSuiteV1 gMessageSuite{};
static OfxMessageSuiteV2 gMessageSuite2{};
static OfxProgressSuiteV1 gProgressSuite{};

static const void* fetchSuite(OfxPropertySetHandle, const char* name, int version) {
    std::string n = name;
    if (n == kOfxPropertySuite && version == 1) return &gPropSuite;
    if (n == kOfxImageEffectSuite && version == 1) return &gEffectSuite;
    if (n == kOfxParameterSuite && version == 1) return &gParamSuite;
    if (n == kOfxMessageSuite && version == 1) return &gMessageSuite;
    if (n == kOfxMessageSuite && version == 2) return &gMessageSuite2;
    if (n == kOfxProgressSuite && version == 1) return &gProgressSuite;
    return nullptr;
}

static OfxHost gHost{H(&gHostProps), fetchSuite};

static void setupSuites() {
    gPropSuite.propSetPointer = propSetPointer;
    gPropSuite.propSetString = propSetString;
    gPropSuite.propSetDouble = propSetDouble;
    gPropSuite.propSetInt = propSetInt;
    gPropSuite.propSetDoubleN = propSetDoubleN;
    gPropSuite.propSetIntN = propSetIntN;
    gPropSuite.propGetPointer = propGetPointer;
    gPropSuite.propGetString = propGetString;
    gPropSuite.propGetDouble = propGetDouble;
    gPropSuite.propGetInt = propGetInt;
    gPropSuite.propGetDoubleN = propGetDoubleN;
    gPropSuite.propGetIntN = propGetIntN;
    gEffectSuite.getPropertySet = getPropertySet;
    gEffectSuite.getParamSet = getParamSet;
    gEffectSuite.clipDefine = clipDefine;
    gEffectSuite.clipGetHandle = clipGetHandle;
    gEffectSuite.clipGetPropertySet = clipGetPropertySet;
    gEffectSuite.clipGetImage = clipGetImage;
    gEffectSuite.clipReleaseImage = clipReleaseImage;
    gEffectSuite.clipGetRegionOfDefinition = clipGetRegionOfDefinition;
    gEffectSuite.abort = effectAbort;
    gParamSuite.paramDefine = paramDefine;
    gParamSuite.paramGetHandle = paramGetHandle;
    gParamSuite.paramGetPropertySet = paramGetPropertySet;
    gParamSuite.paramGetValue = paramGetValue;
    gParamSuite.paramSetValue = paramSetValue;
    gMessageSuite.message = message;
    gMessageSuite2.message = message;
    gMessageSuite2.setPersistentMessage = setPersistentMessage;
    gMessageSuite2.clearPersistentMessage = clearPersistentMessage;
    gProgressSuite.progressStart = progressStart;
    gProgressSuite.progressUpdate = progressUpdate;
    gProgressSuite.progressEnd = progressEnd;
    propSetString(H(&gHostProps), kOfxPropName, 0, "io.keymaster.stubhost");
}

static std::string str(PropSet& set, const char* name, int index = 0) {
    auto it = set.props.find(name);
    if (it == set.props.end() || (int)it->second.s.size() <= index) return std::string();
    return it->second.s[index];
}

static std::unique_ptr<Effect> describe(OfxPlugin* plugin, const char* language) {
    setenv("KEYMASTER_LANGUAGE", language, 1);
    auto effect = std::make_unique<Effect>();
    CHECK_EQ(plugin->mainEntry(kOfxActionDescribe, effect.get(), nullptr, nullptr), kOfxStatOK);
    PropSet ctxArgs;
    propSetString(H(&ctxArgs), kOfxImageEffectPropContext, 0, kOfxImageEffectContextFilter);
    CHECK_EQ(plugin->mainEntry(kOfxImageEffectActionDescribeInContext, effect.get(), H(&ctxArgs), nullptr), kOfxStatOK);
    return effect;
}

static std::unique_ptr<Effect> instantiate(Effect& desc) {
    auto inst = std::make_unique<Effect>();
    propSetString(H(&inst->props), kOfxImageEffectPropContext, 0, kOfxImageEffectContextFilter);
    for (auto& d : desc.params.params) {
        auto p = std::make_unique<Param>();
        p->type = d->type;
        p->name = d->name;
        p->props = d->props;
        auto it = d->props.props.find(kOfxParamPropDefault);
        if (it != d->props.props.end()) {
            if (!it->second.d.empty()) p->d = it->second.d[0];
            if (!it->second.i.empty()) p->i = it->second.i[0];
            if (!it->second.s.empty()) p->s = it->second.s[0];
        }
        inst->params.params.push_back(std::move(p));
    }
    for (auto& [name, d] : desc.clips) {
        auto c = std::make_unique<Clip>();
        c->name = name;
        c->props = d->props;
        c->effect = inst.get();
        OfxPropertySetHandle h = H(&c->props);
        propSetInt(h, kOfxImageClipPropConnected, 0, 1);
        double range[2] = {(double)gFirst, (double)gLast};
        propSetDoubleN(h, kOfxImageEffectPropFrameRange, 2, range);
        propSetDouble(h, kOfxImagePropPixelAspectRatio, 0, 1.0);
        propSetString(h, kOfxImageEffectPropPreMultiplication, 0, kOfxImageOpaque);
        inst->clips[name] = std::move(c);
    }
    return inst;
}

static std::vector<float> render(OfxPlugin* plugin, Effect& inst, double time) {
    PropSet args;
    OfxPropertySetHandle h = H(&args);
    propSetDouble(h, kOfxPropTime, 0, time);
    int window[4] = {0, 0, W, Hh};
    propSetIntN(h, kOfxImageEffectPropRenderWindow, 4, window);
    double scale[2] = {1.0, 1.0};
    propSetDoubleN(h, kOfxImageEffectPropRenderScale, 2, scale);
    propSetString(h, kOfxImageEffectPropFieldToRender, 0, kOfxImageFieldNone);
    CHECK_EQ(plugin->mainEntry(kOfxImageEffectActionRender, &inst, h, nullptr), kOfxStatOK);
    std::vector<float> out = gOutputPixels ? *gOutputPixels : std::vector<float>();
    gReleasedOutputs.clear();
    gOutputPixels = nullptr;
    return out;
}

static bool identity(OfxPlugin* plugin, Effect& inst) {
    PropSet in, out;
    propSetDouble(H(&in), kOfxPropTime, 0, 1.0);
    propSetString(H(&out), kOfxPropName, 0, "");
    OfxStatus st = plugin->mainEntry(kOfxImageEffectActionIsIdentity, &inst, H(&in), H(&out));
    return st == kOfxStatOK && str(out, kOfxPropName) == kOfxImageEffectSimpleSourceClipName;
}

static void press(OfxPlugin* plugin, Effect& inst, const char* name) {
    PropSet args;
    propSetString(H(&args), kOfxPropType, 0, kOfxTypeParameter);
    propSetString(H(&args), kOfxPropName, 0, name);
    propSetString(H(&args), kOfxPropChangeReason, 0, kOfxChangeUserEdited);
    propSetDouble(H(&args), kOfxPropTime, 0, 1.0);
    CHECK_EQ(plugin->mainEntry(kOfxActionInstanceChanged, &inst, H(&args), nullptr), kOfxStatOK);
}

static bool near(float a, float b) { return std::fabs(a - b) < 1e-3f; }

int main() {
    fs::path tmp = fs::path(KM_TEST_TMP) / "plugin";
    fs::remove_all(tmp);
    fs::create_directories(tmp);
    setenv("XDG_CACHE_HOME", (tmp / "cache").c_str(), 1);
    setenv("KEYMASTER_SETTINGS", (tmp / "settings.json").c_str(), 1);

    void* lib = dlopen(KM_BUNDLE_BINARY, RTLD_NOW | RTLD_LOCAL);
    if (!lib) {
        std::fprintf(stderr, "dlopen failed: %s\n", dlerror());
        return 1;
    }
    auto count = reinterpret_cast<int (*)()>(dlsym(lib, "OfxGetNumberOfPlugins"));
    auto get = reinterpret_cast<OfxPlugin* (*)(int)>(dlsym(lib, "OfxGetPlugin"));
    CHECK(count && get);
    if (!count || !get) return finish("plugin");
    CHECK_EQ(count(), 1);
    CHECK(get(1) == nullptr);
    OfxPlugin* plugin = get(0);
    CHECK(plugin != nullptr);
    CHECK_EQ(std::string(plugin->pluginApi), std::string(kOfxImageEffectPluginApi));
    CHECK_EQ(plugin->apiVersion, 1);
    CHECK_EQ(std::string(plugin->pluginIdentifier), std::string("io.github.yoseptf.keymaster"));

    setupSuites();
    plugin->setHost(&gHost);
    CHECK_EQ(plugin->mainEntry(kOfxActionLoad, nullptr, nullptr, nullptr), kOfxStatOK);

    auto es = describe(plugin, "es-419");
    CHECK_EQ(str(es->props, kOfxPropLabel), std::string("Keymaster"));
    CHECK_EQ(str(es->props, kOfxImageEffectPropSupportedContexts, 0), std::string(kOfxImageEffectContextFilter));
    CHECK_EQ(str(es->props, kOfxImageEffectPropSupportedContexts, 1), std::string(kOfxImageEffectContextGeneral));
    CHECK_EQ(str(es->props, kOfxImageEffectPropSupportedPixelDepths), std::string(kOfxBitDepthFloat));
    Param* keyEs = es->params.find("keyClip");
    CHECK(keyEs != nullptr);
    if (keyEs) CHECK_EQ(str(keyEs->props, kOfxPropLabel), std::string("Procesar clip"));
    Param* outEs = es->params.find("output");
    if (outEs) CHECK_EQ(str(outEs->props, kOfxParamPropChoiceOption, 2), std::string("Primer plano"));
    CHECK(es->clips.count(kOfxImageEffectSimpleSourceClipName) == 1);
    CHECK(es->clips.count(kOfxImageEffectOutputClipName) == 1);

    auto en = describe(plugin, "en");
    Param* keyEn = en->params.find("keyClip");
    if (keyEn) CHECK_EQ(str(keyEn->props, kOfxPropLabel), std::string("Key clip"));
    Param* cacheDir = en->params.find("cacheDir");
    CHECK(cacheDir != nullptr);
    if (cacheDir) CHECK_EQ(cacheDir->props.props[kOfxParamPropSecret].i.at(0), 1);
    for (const char* name : {"output", "hintQuality", "despill", "clipEncoding", "clearKey", "keyToken"}) {
        CHECK(en->params.find(name) != nullptr);
    }
    Param* encoding = en->params.find("clipEncoding");
    if (encoding) CHECK_EQ(encoding->props.props[kOfxParamPropDefault].i.at(0), 0);

    auto inst = instantiate(*en);
    CHECK_EQ(plugin->mainEntry(kOfxActionCreateInstance, inst.get(), nullptr, nullptr), kOfxStatOK);
    CHECK(gPersistent.find("Key clip") != std::string::npos);
    CHECK(identity(plugin, *inst));

    auto pass = render(plugin, *inst, 2.0);
    CHECK_EQ(pass.size(), (size_t)W * Hh * 4);
    if (pass.size() == (size_t)W * Hh * 4) {
        CHECK(near(pass[(3 * W + 5) * 4 + 0], sourceValue(5, 3, 0, 2.0)));
        CHECK(near(pass[(3 * W + 5) * 4 + 3], 1.0f));
    }

    unsetenv("KEYMASTER_PYTHON");
    unsetenv("KEYMASTER_CORE");
    gMessages.clear();
    press(plugin, *inst, "keyClip");
    CHECK_EQ(gMessages.size(), (size_t)1);
    if (!gMessages.empty()) CHECK(gMessages[0].find("KEYMASTER_CORE") != std::string::npos);

    setenv("KEYMASTER_PYTHON", KM_PYTHON_BIN, 1);
    setenv("KEYMASTER_CORE", KM_FAKE_CORE, 1);
    gMessages.clear();
    gProgress.clear();
    gProgressLabels.clear();
    press(plugin, *inst, "keyClip");
    for (auto& m : gMessages) std::fprintf(stderr, "unexpected message: %s\n", m.c_str());
    CHECK(gMessages.empty());
    CHECK_EQ(gLiveImages, 0);
    Param* dirParam = inst->params.find("cacheDir");
    Param* tokenParam = inst->params.find("keyToken");
    CHECK(dirParam && !dirParam->s.empty());
    CHECK(tokenParam && !tokenParam->s.empty());
    CHECK(dirParam && dirParam->s.rfind((tmp / "cache" / "keymaster" / "openfx").string(), 0) == 0);
    CHECK(dirParam && fs::exists(fs::path(dirParam->s) / "keymaster-openfx.json"));
    CHECK(dirParam && !fs::exists(fs::path(dirParam->s) / "input"));
    CHECK(!gProgress.empty());
    if (!gProgress.empty()) CHECK_EQ(gProgress.back(), 1.0);
    bool sawCoreLabel = false;
    for (auto& l : gProgressLabels) sawCoreLabel = sawCoreLabel || l == "Keymaster: keying";
    CHECK(sawCoreLabel);
    CHECK(gPersistent.empty());
    CHECK(!identity(plugin, *inst));

    auto cut = render(plugin, *inst, 2.0);
    float a = 200.0f / 255.0f;
    if (cut.size() == (size_t)W * Hh * 4) {
        CHECK(near(cut[3], a));
        CHECK(near(cut[0], a * a));
        CHECK(near(cut[(5 * W + 7) * 4 + 3], a));
    }
    inst->params.find("output")->i = 1;
    auto alpha = render(plugin, *inst, 3.0);
    if (alpha.size() == (size_t)W * Hh * 4) {
        CHECK(near(alpha[0], a));
        CHECK(near(alpha[2], a));
        CHECK(near(alpha[3], 1.0f));
    }
    inst->params.find("output")->i = 2;
    auto fg = render(plugin, *inst, 1.0);
    if (fg.size() == (size_t)W * Hh * 4) {
        CHECK(near(fg[1], a));
        CHECK(near(fg[3], 1.0f));
    }
    inst->params.find("output")->i = 3;
    CHECK(identity(plugin, *inst));
    inst->params.find("output")->i = 0;

    inst->params.find("despill")->d = 0.9;
    press(plugin, *inst, "despill");
    CHECK(gPersistent.find("changed") != std::string::npos);
    CHECK(identity(plugin, *inst));
    inst->params.find("despill")->d = 0.5;
    press(plugin, *inst, "despill");
    CHECK(gPersistent.empty());

    gLast = 5;
    for (auto& [name, clip] : inst->clips) {
        double range[2] = {(double)gFirst, (double)gLast};
        propSetDoubleN(H(&clip->props), kOfxImageEffectPropFrameRange, 2, range);
    }
    press(plugin, *inst, kOfxImageEffectSimpleSourceClipName);
    CHECK(gPersistent.find("changed") != std::string::npos);
    auto stale = render(plugin, *inst, 2.0);
    if (stale.size() == (size_t)W * Hh * 4) CHECK(near(stale[3], 1.0f));

    std::string oldDir = dirParam ? dirParam->s : "";
    press(plugin, *inst, "keyClip");
    CHECK(gPersistent.empty());
    CHECK(dirParam && dirParam->s == oldDir);

    setenv("KEYMASTER_FAKE_FAIL", "no_gpu", 1);
    gMessages.clear();
    press(plugin, *inst, "keyClip");
    unsetenv("KEYMASTER_FAKE_FAIL");
    CHECK_EQ(gMessages.size(), (size_t)1);
    if (!gMessages.empty()) CHECK(gMessages[0].find("core.log") != std::string::npos);
    CHECK(!gPersistent.empty());

    press(plugin, *inst, "keyClip");
    CHECK(gPersistent.empty());
    press(plugin, *inst, "clearKey");
    CHECK(dirParam && dirParam->s.empty());
    CHECK(tokenParam && tokenParam->s.empty());
    CHECK(!oldDir.empty() && !fs::exists(oldDir));
    CHECK(gPersistent.find("Key clip") != std::string::npos);
    CHECK(identity(plugin, *inst));

    CHECK_EQ(plugin->mainEntry(kOfxActionDestroyInstance, inst.get(), nullptr, nullptr), kOfxStatOK);
    CHECK_EQ(plugin->mainEntry(kOfxActionUnload, nullptr, nullptr, nullptr), kOfxStatOK);
    CHECK_EQ(gLiveImages, 0);
    return finish("plugin");
}

#include "frames.hpp"

#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>

#include <stb_image.h>
#include <tinyexr.h>

namespace km {

static void setError(std::string* error, const std::string& text) {
    if (error) *error = text;
}

static std::string takeExrError(const char* err) {
    std::string text = err ? err : "";
    if (err) FreeEXRErrorMessage(err);
    return text;
}

bool writeExrRgb(const fs::path& path, int width, int height, const std::vector<float>& rgb, std::string* error) {
    size_t count = (size_t)width * (size_t)height;
    if (width <= 0 || height <= 0 || rgb.size() < count * 3) {
        setError(error, "bad image size");
        return false;
    }
    std::vector<float> planes[3];
    for (auto& plane : planes) plane.resize(count);
    for (size_t i = 0; i < count; ++i) {
        planes[0][i] = rgb[i * 3 + 2];
        planes[1][i] = rgb[i * 3 + 1];
        planes[2][i] = rgb[i * 3 + 0];
    }
    float* pointers[3] = {planes[0].data(), planes[1].data(), planes[2].data()};

    EXRHeader header;
    InitEXRHeader(&header);
    EXRImage image;
    InitEXRImage(&image);
    image.num_channels = 3;
    image.images = reinterpret_cast<unsigned char**>(pointers);
    image.width = width;
    image.height = height;

    EXRChannelInfo channels[3];
    std::memset(channels, 0, sizeof(channels));
    std::strcpy(channels[0].name, "B");
    std::strcpy(channels[1].name, "G");
    std::strcpy(channels[2].name, "R");
    int pixelTypes[3] = {TINYEXR_PIXELTYPE_FLOAT, TINYEXR_PIXELTYPE_FLOAT, TINYEXR_PIXELTYPE_FLOAT};
    int requested[3] = {TINYEXR_PIXELTYPE_HALF, TINYEXR_PIXELTYPE_HALF, TINYEXR_PIXELTYPE_HALF};
    header.num_channels = 3;
    header.channels = channels;
    header.pixel_types = pixelTypes;
    header.requested_pixel_types = requested;
    header.compression_type = TINYEXR_COMPRESSIONTYPE_ZIP;

    unsigned char* memory = nullptr;
    const char* err = nullptr;
    size_t size = SaveEXRImageToMemory(&image, &header, &memory, &err);
    if (size == 0 || !memory) {
        setError(error, takeExrError(err));
        return false;
    }
    std::string data(reinterpret_cast<char*>(memory), size);
    std::free(memory);
    if (!writeFile(path, data)) {
        setError(error, "cannot write " + u8string(path));
        return false;
    }
    return true;
}

static std::string channelName(const char* name) {
    std::string text(name);
    size_t dot = text.rfind('.');
    if (dot != std::string::npos) text = text.substr(dot + 1);
    if (text.size() == 1) text[0] = (char)std::toupper((unsigned char)text[0]);
    return text;
}

static float sampleChannel(const EXRImage& image, const EXRHeader& header, int channel, size_t index) {
    int type = header.requested_pixel_types[channel];
    if (type == TINYEXR_PIXELTYPE_UINT) return (float)reinterpret_cast<unsigned int**>(image.images)[channel][index];
    return reinterpret_cast<float**>(image.images)[channel][index];
}

static bool readExrScanline(const std::string& data, Image& out, std::string* error) {
    const unsigned char* memory = reinterpret_cast<const unsigned char*>(data.data());
    EXRVersion version;
    if (ParseEXRVersionFromMemory(&version, memory, data.size()) != TINYEXR_SUCCESS || version.multipart ||
        version.non_image) {
        setError(error, "unsupported EXR");
        return false;
    }
    EXRHeader header;
    InitEXRHeader(&header);
    const char* err = nullptr;
    if (ParseEXRHeaderFromMemory(&header, &version, memory, data.size(), &err) != TINYEXR_SUCCESS) {
        setError(error, takeExrError(err));
        return false;
    }
    if (header.tiled) {
        FreeEXRHeader(&header);
        float* rgba = nullptr;
        int width = 0, height = 0;
        if (LoadEXRFromMemory(&rgba, &width, &height, memory, data.size(), &err) != TINYEXR_SUCCESS) {
            setError(error, takeExrError(err));
            return false;
        }
        out.width = width;
        out.height = height;
        out.rgba.assign(rgba, rgba + (size_t)width * height * 4);
        std::free(rgba);
        return true;
    }
    for (int c = 0; c < header.num_channels; ++c) {
        if (header.pixel_types[c] == TINYEXR_PIXELTYPE_HALF) header.requested_pixel_types[c] = TINYEXR_PIXELTYPE_FLOAT;
    }
    EXRImage image;
    InitEXRImage(&image);
    if (LoadEXRImageFromMemory(&image, &header, memory, data.size(), &err) != TINYEXR_SUCCESS) {
        setError(error, takeExrError(err));
        FreeEXRHeader(&header);
        return false;
    }
    int r = -1, g = -1, b = -1, a = -1, y = -1;
    for (int c = 0; c < header.num_channels; ++c) {
        std::string name = channelName(header.channels[c].name);
        if (name == "R" && r < 0) r = c;
        else if (name == "G" && g < 0) g = c;
        else if (name == "B" && b < 0) b = c;
        else if (name == "A" && a < 0) a = c;
        else if (name == "Y" && y < 0) y = c;
    }
    bool single = header.num_channels == 1;
    if (r < 0 || g < 0 || b < 0) {
        int gray = y >= 0 ? y : (single ? 0 : (a >= 0 ? a : 0));
        r = g = b = gray;
        if (single && a < 0) a = 0;
    }
    out.width = image.width;
    out.height = image.height;
    size_t count = (size_t)image.width * image.height;
    out.rgba.resize(count * 4);
    for (size_t i = 0; i < count; ++i) {
        out.rgba[i * 4 + 0] = sampleChannel(image, header, r, i);
        out.rgba[i * 4 + 1] = sampleChannel(image, header, g, i);
        out.rgba[i * 4 + 2] = sampleChannel(image, header, b, i);
        out.rgba[i * 4 + 3] = a >= 0 ? sampleChannel(image, header, a, i) : 1.0f;
    }
    FreeEXRImage(&image);
    FreeEXRHeader(&header);
    return true;
}

static bool readPng(const std::string& data, Image& out, std::string* error) {
    int width = 0, height = 0, comp = 0;
    stbi_us* pixels = stbi_load_16_from_memory(reinterpret_cast<const stbi_uc*>(data.data()), (int)data.size(),
                                               &width, &height, &comp, 0);
    if (!pixels) {
        setError(error, stbi_failure_reason() ? stbi_failure_reason() : "cannot decode image");
        return false;
    }
    out.width = width;
    out.height = height;
    size_t count = (size_t)width * height;
    out.rgba.resize(count * 4);
    for (size_t i = 0; i < count; ++i) {
        const stbi_us* p = pixels + i * comp;
        float v[4];
        for (int c = 0; c < comp; ++c) v[c] = p[c] / 65535.0f;
        float* o = &out.rgba[i * 4];
        if (comp == 1) {
            o[0] = o[1] = o[2] = o[3] = v[0];
        } else if (comp == 2) {
            o[0] = o[1] = o[2] = v[0];
            o[3] = v[1];
        } else {
            o[0] = v[0];
            o[1] = v[1];
            o[2] = v[2];
            o[3] = comp == 4 ? v[3] : 1.0f;
        }
    }
    stbi_image_free(pixels);
    return true;
}

bool readImage(const fs::path& path, Image& image, std::string* error) {
    std::string data;
    if (!readFile(path, data)) {
        setError(error, "cannot read " + u8string(path));
        return false;
    }
    image = Image();
    if (data.size() >= 4 && (unsigned char)data[0] == 0x76 && (unsigned char)data[1] == 0x2f &&
        (unsigned char)data[2] == 0x31 && (unsigned char)data[3] == 0x01) {
        image.linear = true;
        return readExrScanline(data, image, error);
    }
    image.linear = false;
    return readPng(data, image, error);
}

float linearToSrgb(float value) {
    float sign = value < 0.0f ? -1.0f : 1.0f;
    float x = std::fabs(value);
    float y = x <= 0.0031308f ? 12.92f * x : 1.055f * std::pow(x, 1.0f / 2.4f) - 0.055f;
    return sign * y;
}

float srgbToLinear(float value) {
    float sign = value < 0.0f ? -1.0f : 1.0f;
    float x = std::fabs(value);
    float y = x <= 0.04045f ? x / 12.92f : std::pow((x + 0.055f) / 1.055f, 2.4f);
    return sign * y;
}

}

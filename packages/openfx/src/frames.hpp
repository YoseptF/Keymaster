#pragma once

#include <string>
#include <vector>

#include "paths.hpp"

namespace km {

struct Image {
    int width = 0;
    int height = 0;
    bool linear = false;
    std::vector<float> rgba;
};

bool writeExrRgb(const fs::path& path, int width, int height, const std::vector<float>& rgb, std::string* error);
bool readImage(const fs::path& path, Image& image, std::string* error);
float linearToSrgb(float value);
float srgbToLinear(float value);

}

#include <cmath>
#include <cstdlib>

#include <miniz.h>

#include "check.hpp"
#include "frames.hpp"

using namespace km;

static bool near(float a, float b, float tol) { return std::fabs(a - b) <= tol; }

static void writePng(const fs::path& path, int w, int h, int channels, unsigned char value) {
    std::vector<unsigned char> pixels((size_t)w * h * channels, value);
    pixels[0] = 10;
    size_t size = 0;
    void* png = tdefl_write_image_to_png_file_in_memory(pixels.data(), w, h, channels, &size);
    writeFile(path, std::string(static_cast<char*>(png), size));
    mz_free(png);
}

int main() {
    fs::path dir = fs::path(KM_TEST_TMP) / "frames";
    fs::remove_all(dir);
    fs::create_directories(dir);

    int w = 5, h = 3;
    std::vector<float> rgb((size_t)w * h * 3);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
            for (int c = 0; c < 3; ++c) rgb[((size_t)y * w + x) * 3 + c] = 0.1f * x + 0.25f * y + 0.01f * c;
    rgb[0] = 4.5f;
    rgb[1] = -0.25f;
    std::string err;
    CHECK(writeExrRgb(dir / "f.exr", w, h, rgb, &err));
    Image img;
    CHECK(readImage(dir / "f.exr", img, &err));
    CHECK(img.linear);
    CHECK_EQ(img.width, w);
    CHECK_EQ(img.height, h);
    bool same = true;
    for (int i = 0; i < w * h; ++i) {
        for (int c = 0; c < 3; ++c) same = same && near(img.rgba[i * 4 + c], rgb[i * 3 + c], 0.005f);
        same = same && img.rgba[i * 4 + 3] == 1.0f;
    }
    CHECK(same);
    CHECK(!writeExrRgb(dir / "bad.exr", 0, 0, rgb, &err));
    CHECK(!readImage(dir / "missing.exr", img, &err));
    writeFile(dir / "junk.png", "not an image");
    CHECK(!readImage(dir / "junk.png", img, &err));

    writePng(dir / "a.png", 16, 9, 1, 200);
    CHECK(readImage(dir / "a.png", img, &err));
    CHECK(!img.linear);
    CHECK_EQ(img.width, 16);
    CHECK_EQ(img.height, 9);
    CHECK(near(img.rgba[0], 10 / 255.0f, 1e-4f));
    CHECK(near(img.rgba[3], 10 / 255.0f, 1e-4f));
    CHECK(near(img.rgba[4], 200 / 255.0f, 1e-4f));
    CHECK(near(img.rgba[7], 200 / 255.0f, 1e-4f));

    writePng(dir / "fg.png", 4, 2, 3, 128);
    CHECK(readImage(dir / "fg.png", img, &err));
    CHECK(near(img.rgba[4 + 1], 128 / 255.0f, 1e-4f));
    CHECK_EQ(img.rgba[3], 1.0f);

    writePng(dir / "cut.png", 4, 2, 4, 51);
    CHECK(readImage(dir / "cut.png", img, &err));
    CHECK(near(img.rgba[7], 51 / 255.0f, 1e-4f));

    for (float v : {0.0f, 0.001f, 0.18f, 0.5f, 1.0f, 2.5f, -0.2f}) {
        CHECK(near(srgbToLinear(linearToSrgb(v)), v, 1e-4f));
    }
    CHECK(near(linearToSrgb(0.18f), 0.4613f, 1e-3f));
    CHECK(near(srgbToLinear(0.5f), 0.2140f, 1e-3f));
    return finish("frames");
}

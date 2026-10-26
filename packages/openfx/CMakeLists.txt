cmake_minimum_required(VERSION 3.16)
project(KeymasterOFX LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_C_VISIBILITY_PRESET hidden)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

set(KEYMASTER_VERSION "0.0.0" CACHE STRING "Plugin version")
option(KEYMASTER_TESTS "Build the unit tests" ON)

string(REGEX MATCH "^([0-9]+)\\.([0-9]+)\\.([0-9]+)" _km_version "${KEYMASTER_VERSION}")
set(KM_MAJOR ${CMAKE_MATCH_1})
set(KM_MINOR ${CMAKE_MATCH_2})
set(KM_PATCH ${CMAKE_MATCH_3})
if(NOT _km_version)
  set(KM_MAJOR 0)
  set(KM_MINOR 0)
  set(KM_PATCH 0)
endif()

if(WIN32)
  set(KM_ARCH_DIR Win64)
else()
  set(KM_ARCH_DIR Linux-x86-64)
endif()

set(VENDOR ${CMAKE_CURRENT_SOURCE_DIR}/vendor)

add_library(km_miniz STATIC ${VENDOR}/miniz/miniz.c)
target_include_directories(km_miniz PUBLIC ${VENDOR}/miniz)
target_compile_definitions(km_miniz PUBLIC MINIZ_NO_ARCHIVE_APIS MINIZ_NO_STDIO MINIZ_NO_TIME)

add_library(km_common STATIC
  src/paths.cpp
  src/settings.cpp
  src/i18n.cpp
  src/events.cpp
  src/cache.cpp
  src/frames.cpp
  src/process.cpp
  src/vendor_impl.cpp)
set_source_files_properties(src/vendor_impl.cpp ${VENDOR}/miniz/miniz.c PROPERTIES COMPILE_OPTIONS "-w")
target_include_directories(km_common PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/src
  ${VENDOR}
  ${VENDOR}/tinyexr
  ${VENDOR}/stb
  ${VENDOR}/openfx/include)
target_compile_definitions(km_common PUBLIC TINYEXR_USE_MINIZ=1 TINYEXR_USE_OPENMP=0 TINYEXR_USE_THREAD=0 NOMINMAX WIN32_LEAN_AND_MEAN)
target_link_libraries(km_common PUBLIC km_miniz ${CMAKE_DL_LIBS})

add_library(Keymaster MODULE src/plugin.cpp)
target_link_libraries(Keymaster PRIVATE km_common)
target_compile_definitions(Keymaster PRIVATE
  KM_VERSION_MAJOR=${KM_MAJOR}
  KM_VERSION_MINOR=${KM_MINOR}
  KM_VERSION_PATCH=${KM_PATCH}
  KM_VERSION_STRING="${KEYMASTER_VERSION}")
set_target_properties(Keymaster PROPERTIES PREFIX "" SUFFIX ".ofx" OUTPUT_NAME "Keymaster" CXX_VISIBILITY_PRESET default)

if(WIN32)
  target_link_options(Keymaster PRIVATE -static -static-libgcc -static-libstdc++ $<$<CONFIG:Release>:-s>)
else()
  target_link_options(Keymaster PRIVATE
    -static-libgcc -static-libstdc++
    -Wl,--exclude-libs,ALL
    -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/cmake/exports.map
    -Wl,--no-undefined
    $<$<CONFIG:Release>:-s>)
endif()

set(KM_BUNDLE ${CMAKE_BINARY_DIR}/Keymaster.ofx.bundle)
add_custom_command(TARGET Keymaster POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E make_directory ${KM_BUNDLE}/Contents/${KM_ARCH_DIR}
  COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:Keymaster> ${KM_BUNDLE}/Contents/${KM_ARCH_DIR}/Keymaster.ofx
  COMMAND ${CMAKE_COMMAND} -E make_directory ${KM_BUNDLE}/Contents/Resources/i18n/openfx ${KM_BUNDLE}/Contents/Resources/i18n/core
  COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_CURRENT_SOURCE_DIR}/i18n/en.json ${CMAKE_CURRENT_SOURCE_DIR}/i18n/es-419.json ${KM_BUNDLE}/Contents/Resources/i18n/openfx/
  COMMAND ${CMAKE_COMMAND} -E copy ${CMAKE_CURRENT_SOURCE_DIR}/../core/i18n/en.json ${CMAKE_CURRENT_SOURCE_DIR}/../core/i18n/es-419.json ${KM_BUNDLE}/Contents/Resources/i18n/core/
  VERBATIM)

if(KEYMASTER_TESTS AND NOT CMAKE_CROSSCOMPILING)
  enable_testing()
  add_subdirectory(tests)
endif()

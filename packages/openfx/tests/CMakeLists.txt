set(KM_TEST_TMP ${CMAKE_BINARY_DIR}/test-tmp)
set(KM_REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../..)
find_package(Python3 COMPONENTS Interpreter)

foreach(name events settings i18n cache frames process)
  add_executable(test_${name} test_${name}.cpp)
  target_link_libraries(test_${name} PRIVATE km_common)
  target_compile_definitions(test_${name} PRIVATE
    KM_TEST_TMP="${KM_TEST_TMP}"
    KM_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/.."
    KM_REPO_ROOT="${KM_REPO_ROOT}"
    KM_PYTHON="${Python3_EXECUTABLE}")
  add_test(NAME ${name} COMMAND test_${name})
endforeach()

add_executable(test_plugin test_plugin.cpp)
target_include_directories(test_plugin PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../vendor/openfx/include ${CMAKE_CURRENT_SOURCE_DIR}/../vendor)
target_link_libraries(test_plugin PRIVATE ${CMAKE_DL_LIBS})
add_dependencies(test_plugin Keymaster)
target_compile_definitions(test_plugin PRIVATE
  KM_BUNDLE_BINARY="${CMAKE_BINARY_DIR}/Keymaster.ofx.bundle/Contents/${KM_ARCH_DIR}/Keymaster.ofx"
  KM_TEST_TMP="${KM_TEST_TMP}"
  KM_PYTHON_BIN="${Python3_EXECUTABLE}"
  KM_FAKE_CORE="${KM_REPO_ROOT}/packages/core/testing/fake_core")
add_test(NAME plugin COMMAND test_plugin)

cmake_minimum_required(VERSION 3.15)
project(AVFramework VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# FFmpeg 路径
set(FFMPEG_ROOT "C:/Users/1000003244/Downloads/ffmpeg-master-latest-win64-gpl-shared/ffmpeg-master-latest-win64-gpl-shared")

# 设置头文件路径
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${FFMPEG_ROOT}/include
)

# 设置库文件路径
link_directories(
    ${FFMPEG_ROOT}/lib
)

# 简化版源文件（仅测试 FFmpeg）
add_executable(${PROJECT_NAME}
    src/main.cpp
)

# 链接 FFmpeg 库
target_link_libraries(${PROJECT_NAME}
    avcodec
    avformat
    avutil
)

# 复制 DLL 到输出目录
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${FFMPEG_ROOT}/bin
        $<TARGET_FILE_DIR:${PROJECT_NAME}>
    COMMENT "Copying FFmpeg DLLs to output directory"
)

# 设置输出目录
set_target_properties(${PROJECT_NAME} PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

message(STATUS "========================================")
message(STATUS "  AVFramework Configuration")
message(STATUS "========================================")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "Standard: C++${CMAKE_CXX_STANDARD}")
message(STATUS "FFmpeg: ${FFMPEG_ROOT}")
message(STATUS "========================================")

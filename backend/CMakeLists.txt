cmake_minimum_required(VERSION 3.15)
project(AVFramework VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(BUILD_SCREENSHARE "Build screen share server" ON)

# 头文件路径
include_directories(
    ${CMAKE_SOURCE_DIR}/include
)

# ========== 跨平台 FFmpeg 查找 ==========
if(APPLE)
    set(FFMPEG_ROOT "/opt/homebrew")
elseif(UNIX)
    set(FFMPEG_ROOT "/usr/local")
endif()

if(APPLE OR UNIX)
    include_directories(${FFMPEG_ROOT}/include)
    link_directories(${FFMPEG_ROOT}/lib)
endif()

# ========== FFmpeg 测试程序 ==========
add_executable(avframework
    src/main.cpp
)

if(APPLE OR UNIX)
    target_link_libraries(avframework
        avcodec
        avformat
        avutil
    )
elseif(WIN32)
    set(FFMPEG_WIN "C:/Users/1000003244/Downloads/ffmpeg-master-latest-win64-gpl-shared/ffmpeg-master-latest-win64-gpl-shared")
    include_directories(${FFMPEG_WIN}/include)
    link_directories(${FFMPEG_WIN}/lib)
    target_link_libraries(avframework avcodec avformat avutil)

    add_custom_command(TARGET avframework POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            ${FFMPEG_WIN}/bin
            $<TARGET_FILE_DIR:avframework>
        COMMENT "Copying FFmpeg DLLs to output directory"
    )
endif()

set_target_properties(avframework PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# ========== 屏幕共享服务器 ==========
if(BUILD_SCREENSHARE)
    if(APPLE)
        set(OPENSSL_ROOT_DIR "/opt/homebrew/opt/openssl@3")
    elseif(UNIX)
        set(OPENSSL_ROOT_DIR "/usr/local/opt/openssl@3")
    endif()

    find_package(OpenSSL REQUIRED)
    include_directories(${OPENSSL_INCLUDE_DIR})

    add_executable(screenshare-server
        src/screen_share_main.cpp
        src/webrtc/signaling_server.cpp
        src/api/websocket_server.cpp
        src/utils/logger.cpp
    )

    if(WIN32)
        target_link_libraries(screenshare-server ws2_32)
    else()
        target_link_libraries(screenshare-server OpenSSL::SSL OpenSSL::Crypto pthread)
    endif()

    set_target_properties(screenshare-server PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()

message(STATUS "========================================")
message(STATUS "  AVFramework Configuration")
message(STATUS "========================================")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "Standard: C++${CMAKE_CXX_STANDARD}")
message(STATUS "Platform: ${CMAKE_SYSTEM_NAME}")
message(STATUS "FFmpeg: ${FFMPEG_ROOT}")
if(BUILD_SCREENSHARE)
    message(STATUS "OpenSSL: ${OPENSSL_INCLUDE_DIR}")
    message(STATUS "ScreenShare: ON")
endif()
message(STATUS "========================================")

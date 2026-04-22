#include <iostream>
#include <memory>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
}

int main(int argc, char* argv[]) {
    std::cout << "\n========================================\n";
    std::cout << "   AVFramework - FFmpeg Test\n";
    std::cout << "========================================\n\n";

    // 打印 FFmpeg 版本信息
    std::cout << "FFmpeg Configuration Test:\n";
    std::cout << "  avcodec configuration: " << avcodec_configuration() << "\n";
    std::cout << "  avcodec version: " << avcodec_version() << "\n";
    std::cout << "  avformat version: " << avformat_version() << "\n";
    std::cout << "  avutil version: " << avutil_version() << "\n";

    std::cout << "\n========================================\n";
    std::cout << "FFmpeg Test Complete!\n";
    std::cout << "========================================\n\n";

    std::cout << "Your FFmpeg environment is working correctly!\n";
    std::cout << "You can now develop video processing applications.\n\n";

    return 0;
}

#pragma once

#include "av_common.h"
#include "av_decoder.h"
#include "av_encoder.h"
#include <memory>
#include <atomic>

namespace avframework {

class AVProcessor {
public:
    AVProcessor();
    ~AVProcessor();

    AVResult init(const AVConfig& input_config, const AVConfig& output_config);
    void cleanup();

    AVResult startTranscode(const std::string& input_url, const std::string& output_url);
    void stop();
    bool isRunning() const { return running_; }

    void setProgressCallback(std::function<void(double)> callback) {
        progress_callback_ = std::move(callback);
    }

private:
    void processLoop();
    void applyFilters(AVFrame* frame);

    std::unique_ptr<AVDecoder> decoder_;
    std::unique_ptr<AVEncoder> encoder_;

    AVConfig input_config_;
    AVConfig output_config_;

    std::atomic<bool> running_;
    std::atomic<bool> should_stop_;

    std::function<void(double)> progress_callback_;

    struct SwsContext* sws_ctx_;
    struct SwrContext* swr_ctx_;
};

}

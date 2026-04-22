export class API {
  constructor(baseURL = '') {
    this.baseURL = baseURL;
  }

  async request(url, options = {}) {
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    };

    try {
      const response = await fetch(`${this.baseURL}${url}`, config);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }

      return await response.text();

    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async get(url, options = {}) {
    return this.request(url, { ...options, method: 'GET' });
  }

  async post(url, data, options = {}) {
    return this.request(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async put(url, data, options = {}) {
    return this.request(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  async delete(url, options = {}) {
    return this.request(url, { ...options, method: 'DELETE' });
  }

  async getStreams() {
    const response = await this.get('/api/streams');
    return response.streams || [];
  }

  async getStream(streamId) {
    const response = await this.get(`/api/streams/${streamId}`);
    return response;
  }

  async createStream(streamId, config = {}) {
    return this.post('/api/streams', {
      stream_id: streamId,
      width: config.width || 1920,
      height: config.height || 1080,
      fps: config.fps || 30
    });
  }

  async deleteStream(streamId) {
    return this.delete(`/api/streams/${streamId}`);
  }

  async startStream(streamId, sourceUrl) {
    return this.post(`/api/streams/${streamId}/start`, {
      source_url: sourceUrl
    });
  }

  async stopStream(streamId) {
    return this.post(`/api/streams/${streamId}/stop`);
  }

  async startTranscode(inputUrl, outputUrl, config = {}) {
    return this.post('/api/transcode', {
      input_url: inputUrl,
      output_url: outputUrl,
      output_width: config.width || 1920,
      output_height: config.height || 1080,
      output_fps: config.fps || 30
    });
  }

  async uploadVideo(file, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } else {
          reject(new Error(`Upload failed: ${xhr.statusText}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'));
      });

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload aborted'));
      });

      const formData = new FormData();
      formData.append('video', file);

      xhr.open('POST', `${this.baseURL}/api/upload`);
      xhr.send(formData);
    });
  }

  async uploadVideoChunk(file, chunkSize = 1024 * 1024, onProgress) {
    const chunks = Math.ceil(file.size / chunkSize);
    let uploadedChunks = 0;

    for (let i = 0; i < chunks; i++) {
      const start = i * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const chunk = file.slice(start, end);

      const formData = new FormData();
      formData.append('chunk', chunk);
      formData.append('chunk_index', i);
      formData.append('total_chunks', chunks);
      formData.append('file_name', file.name);
      formData.append('file_size', file.size);

      await this.post('/api/upload-chunk', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      uploadedChunks++;

      if (onProgress) {
        const progress = Math.round((uploadedChunks / chunks) * 100);
        onProgress(progress);
      }
    }

    return { success: true };
  }
}

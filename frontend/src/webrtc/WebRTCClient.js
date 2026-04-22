export class WebRTCClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.pc = null;
    this.localStream = null;
    this.remoteStream = null;
    this.sessionId = null;
    this.isCaller = false;

    this.config = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    };

    this.events = {};
  }

  on(event, callback) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(callback);
  }

  emit(event, data) {
    if (this.events[event]) {
      this.events[event].forEach(callback => callback(data));
    }
  }

  async start() {
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 30 }
        },
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      await this.connect();
      await this.createSession();

    } catch (error) {
      throw new Error('Failed to start: ' + error.message);
    }
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.setupMessageHandler();
        resolve();
      };

      this.ws.onerror = (error) => {
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
      };
    });
  }

  setupMessageHandler() {
    this.ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);

        switch (message.type) {
          case 'session_created':
            this.sessionId = message.session_id;
            console.log('Session created:', this.sessionId);
            break;

          case 'session_joined':
            if (message.success) {
              console.log('Joined session:', this.sessionId);
            }
            break;

          case 'offer':
            await this.handleOffer(message.sdp);
            break;

          case 'answer':
            await this.handleAnswer(message.sdp);
            break;

          case 'ice':
            await this.handleICECandidate(message.candidate);
            break;
        }

      } catch (error) {
        console.error('Message handling error:', error);
      }
    };
  }

  async createSession() {
    this.isCaller = true;
    this.send({ type: 'create_session' });
  }

  async joinSession(sessionId) {
    this.isCaller = false;
    this.sessionId = sessionId;
    this.send({
      type: 'join_session',
      session_id: sessionId
    });
  }

  createPeerConnection() {
    this.pc = new RTCPeerConnection(this.config);

    this.localStream.getTracks().forEach(track => {
      this.pc.addTrack(track, this.localStream);
    });

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.send({
          type: 'ice_candidate',
          session_id: this.sessionId,
          candidate: JSON.stringify(event.candidate)
        });
      }
    };

    this.pc.ontrack = (event) => {
      this.emit('track', event);
      const [remoteStream] = event.streams;
      this.remoteStream = remoteStream;
    };

    this.pc.onconnectionstatechange = () => {
      console.log('Connection state:', this.pc.connectionState);
      this.emit('statechange', this.pc.connectionState);
    };
  }

  async createOffer() {
    this.createPeerConnection();

    const offer = await this.pc.createOffer({
      offerToReceiveAudio: true,
      offerToReceiveVideo: true
    });

    await this.pc.setLocalDescription(offer);

    this.send({
      type: 'offer',
      session_id: this.sessionId,
      sdp: JSON.stringify(offer)
    });
  }

  async handleOffer(sdpString) {
    this.createPeerConnection();

    const offer = JSON.parse(sdpString);
    await this.pc.setRemoteDescription(new RTCSessionDescription(offer));

    const answer = await this.pc.createAnswer();
    await this.pc.setLocalDescription(answer);

    this.send({
      type: 'answer',
      session_id: this.sessionId,
      sdp: JSON.stringify(answer)
    });
  }

  async handleAnswer(sdpString) {
    const answer = JSON.parse(sdpString);
    await this.pc.setRemoteDescription(new RTCSessionDescription(answer));
  }

  async handleICECandidate(candidateString) {
    const candidate = JSON.parse(candidateString);
    await this.pc.addIceCandidate(new RTCIceCandidate(candidate));
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  async toggleAudio(enabled) {
    if (this.localStream) {
      this.localStream.getAudioTracks().forEach(track => {
        track.enabled = enabled;
      });
    }
  }

  async toggleVideo(enabled) {
    if (this.localStream) {
      this.localStream.getVideoTracks().forEach(track => {
        track.enabled = enabled;
      });
    }
  }

  async replaceCamera(constraints = {}) {
    if (!this.localStream) return;

    const videoTrack = this.localStream.getVideoTracks()[0];
    if (!videoTrack) return;

    try {
      const newStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 30 },
          ...constraints
        }
      });

      const newVideoTrack = newStream.getVideoTracks()[0];

      const sender = this.pc.getSenders().find(s =>
        s.track && s.track.kind === 'video'
      );

      if (sender) {
        await sender.replaceTrack(newVideoTrack);
      }

      videoTrack.stop();
      this.localStream.removeTrack(videoTrack);
      this.localStream.addTrack(newVideoTrack);

    } catch (error) {
      console.error('Failed to replace camera:', error);
    }
  }

  getStats(callback) {
    if (this.pc) {
      this.pc.getStats().then(stats => {
        callback(stats);
      });
    }
  }

  stop() {
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop());
      this.localStream = null;
    }

    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.remoteStream = null;
  }
}

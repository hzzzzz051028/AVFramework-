// 屏幕共享 WebRTC 客户端
export class ScreenShareClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.pc = null;
    localStream = null;
    remoteStream = null;
    this.sessionId = null;
    this.isSharing = false;

    this.config = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    };
  }

  async startScreenShare() {
    try {
      // 获取屏幕共享流
      this.localStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          cursor: "always"
        },
        audio: false
      });

      await this.connect();
      await this.createSession();
      this.isSharing = true;

    } catch (error) {
      console.error('Failed to start screen share:', error);
      throw error;
    }
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('✅ WebSocket connected');
        this.setupMessageHandler();
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('❌ WebSocket connection failed');
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
      };
    });
  }

  setupMessageHandler() {
    this.ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('📨 Received:', message.type);

        switch (message.type) {
          case 'session_created':
            this.sessionId = message.session_id;
            console.log('🎫 Session created:', this.sessionId);
            this.onSessionCreated?.(this.sessionId);
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
    this.createPeerConnection();

    const offer = await this.pc.createOffer({
      offerToReceiveVideo: false,
      offerToReceiveAudio: false
    });

    await this.pc.setLocalDescription(offer);

    this.send({
      type: 'create_session',
      offer: JSON.stringify(offer)
    });
  }

  async joinSession(sessionId) {
    this.sessionId = sessionId;
    this.createPeerConnection();

    this.send({
      type: 'join_session',
      session_id: sessionId
    });
  }

  createPeerConnection() {
    this.pc = new RTCPeerConnection(this.config);

    // 添加屏幕共享流
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => {
        this.pc.addTrack(track, this.localStream);
      });
    }

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
      console.log('📹 Received remote track');
      const [remoteStream] = event.streams;
      this.remoteStream = remoteStream;
      this.onRemoteStream?.(remoteStream);
    };

    this.pc.onconnectionstatechange = () => {
      console.log('🔄 Connection state:', this.pc.connectionState);
      this.onStateChange?.(this.pc.connectionState);
    };
  }

  async handleOffer(sdpString) {
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

  stop() {
    console.log('🛑 Stopping screen share');

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

    this.isSharing = false;
  }

  // 回调函数
  onSessionCreated = null;
  onRemoteStream = null;
  onStateChange = null;
}

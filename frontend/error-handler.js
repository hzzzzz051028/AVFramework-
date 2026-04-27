/**
 * 错误处理和提示模块
 * 为常见错误提供友好的提示和解决方案
 */

class ErrorHandler {
  constructor() {
    this.errorMessages = {
      // 屏幕共享相关
      'PermissionDeniedError': {
        title: '屏幕共享权限被拒绝',
        message: '请允许浏览器访问您的屏幕',
        solution: '点击地址栏左侧的锁图标，允许屏幕共享权限'
      },
      'NotAllowedError': {
        title: '操作被取消',
        message: '您取消了屏幕共享',
        solution: '请重新点击"开始投屏"按钮并选择要共享的屏幕'
      },
      'NotFoundError': {
        title: '未找到屏幕/窗口',
        message: '没有可用的屏幕或窗口',
        solution: '请确保您的设备已连接，或尝试重启浏览器'
      },
      'InvalidStateError': {
        title: '浏览器状态异常',
        message: '浏览器当前状态不允许此操作',
        solution: '请刷新页面后重试'
      },

      // 网络相关
      'NetworkError': {
        title: '网络连接失败',
        message: '无法连接到投屏设备',
        solution: '请检查：1. 网络连接是否正常 2. 投屏设备是否开机 3. 防火墙设置'
      },
      'TimeoutError': {
        title: '连接超时',
        message: '连接设备超时',
        solution: '请检查网络连接，或尝试刷新设备列表'
      },

      // WebRTC 相关
      'ICEError': {
        title: 'P2P 连接失败',
        message: '无法建立点对点连接',
        solution: '请检查：1. 是否在同一局域网 2. STUN 服务器是否可用'
      },
      'SDPError': {
        title: '媒体协商失败',
        message: '无法与设备协商媒体格式',
        solution: '请尝试刷新页面或更换浏览器'
      },

      // 通用错误
      'default': {
        title: '发生错误',
        message: '未知错误',
        solution: '请刷新页面重试，或查看控制台获取更多信息'
      }
    };
  }

  /**
   * 处理错误并显示友好提示
   */
  handleError(error, context = '') {
    console.error('[ErrorHandler]', context, error);

    const errorInfo = this.getErrorInfo(error);
    this.showErrorDialog(errorInfo, context);
  }

  /**
   * 获取错误信息
   */
  getErrorInfo(error) {
    const errorName = error.name || error.constructor.name;
    return this.errorMessages[errorName] || this.errorMessages['default'];
  }

  /**
   * 显示错误对话框
   */
  showErrorDialog(errorInfo, context) {
    // 创建对话框元素
    const dialog = document.createElement('div');
    dialog.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    `;

    dialog.innerHTML = `
      <div style="
        background: #1e293b;
        border-radius: 12px;
        padding: 2rem;
        max-width: 500px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        animation: slideIn 0.3s ease-out;
      ">
        <div style="
          display: flex;
          align-items: center;
          margin-bottom: 1rem;
        ">
          <div style="
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: #fee2e2;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 1rem;
          ">
            <svg style="width: 24px; height: 24px; color: #dc2626;" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-9a1 1 0 10-2 0 1 1 0 002 0zm-1 4a1 1 0 10-2 0 1 1 0 002 0z" clip-rule="evenodd"/>
            </svg>
          </div>
          <div>
            <h3 style="color: #f87171; font-size: 1.2rem; margin: 0;">${errorInfo.title}</h3>
            <p style="color: #94a3b8; margin: 0.25rem 0 0 0;">${errorInfo.message}</p>
          </div>
        </div>

        ${errorInfo.solution ? `
          <div style="
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1.5rem;
          ">
            <div style="color: #3b82f6; font-weight: 500; margin-bottom: 0.5rem; font-size: 0.9rem;">解决方法：</div>
            <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.5;">${errorInfo.solution}</div>
          </div>
        ` : ''}

        ${context ? `
          <div style="
            background: rgba(234, 179, 8, 0.1);
            border-left: 3px solid #eab308;
            padding: 0.75rem;
            margin-bottom: 1.5rem;
            font-size: 0.85rem;
            color: #eab308;
          ">
            <strong>错误位置：</strong> ${context}
          </div>
        ` : ''}

        <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
          <button onclick="location.reload()" style="
            padding: 0.6rem 1.2rem;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
          ">刷新页面</button>
          <button onclick="this.closest('div[style*=fixed]').remove()" style="
            padding: 0.6rem 1.2rem;
            background: transparent;
            color: #94a3b8;
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
          ">关闭</button>
        </div>
      </div>
    `;

    // 添加动画
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from {
          opacity: 0;
          transform: translateY(-20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
    `;
    document.head.appendChild(style);

    document.body.appendChild(dialog);
  }
}

// 创建全局错误处理器
window.errorHandler = new ErrorHandler();

// 全局错误监听
window.addEventListener('error', (event) => {
  window.errorHandler.handleError(event.error, event.message);
});

window.addEventListener('unhandledrejection', (event) => {
  window.errorHandler.handleError(event.reason, 'Promise rejection');
});

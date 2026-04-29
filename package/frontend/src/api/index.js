import axios from 'axios';

// API 基础路径配置
// 开发环境和生产环境都使用 /api 前缀
// 后端路由在 main.py 中以 /api 为前缀注册
const getBaseURL = () => {
  return '/api';
};

const api = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000, // 默认30秒超时，各端点可单独覆盖
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const userToken = localStorage.getItem('userToken');
    if (userToken) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${userToken}`,
      };
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('userToken');
      if (!window.location.pathname.startsWith('/admin')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
  updateProfile: (data) => api.patch('/auth/me', data),
};

// User account API
export const userAPI = {
  getCredits: () => api.get('/user/credits'),
  redeemCode: (code) => api.post('/user/redeem-code', { code }),
  getMyInvite: () => api.get('/user/invites/my'),
  createMyInvite: () => api.post('/user/invites'),
  listCreditTransactions: (limit = 50) => api.get('/user/credit-transactions', { params: { limit } }),
  getProviderConfig: () => api.get('/user/provider-config'),
  saveProviderConfig: (data) => api.put('/user/provider-config', data),
  testProviderConfig: () => api.post('/user/provider-config/test'),
};

// Paper project API
export const projectAPI = {
  list: () => api.get('/user/projects'),
  create: (data) => api.post('/user/projects', data),
  update: (projectId, data) => api.patch(`/user/projects/${projectId}`, data),
  archive: (projectId) => api.delete(`/user/projects/${projectId}`),
};

// Optimization API
export const optimizationAPI = {
  startOptimization: (data) => api.post('/optimization/start', data, {
    timeout: 60000, // 启动任务延长到60秒超时
  }),
  getQueueStatus: (sessionId = null) =>
    api.get('/optimization/status', {
      params: sessionId ? { session_id: sessionId } : {},
      timeout: 10000, // 10秒超时
    }),
  listSessions: (projectId = null) => api.get('/optimization/sessions', {
    params: projectId !== null ? { project_id: projectId } : {},
    timeout: 15000, // 15秒超时
  }),
  getSessionDetail: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}`, {
      timeout: 20000, // 20秒超时
    }),
  getSessionProgress: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}/progress`, {
      timeout: 10000, // 10秒超时
    }),
  getSessionChanges: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}/changes`, {
      timeout: 20000, // 20秒超时
    }),
  stopSession: (sessionId) =>
    api.post(`/optimization/sessions/${sessionId}/stop`, null, {
      timeout: 10000, // 10秒超时
    }),
  exportSession: (sessionId, confirmation) =>
    api.post(`/optimization/sessions/${sessionId}/export`, confirmation, {
      timeout: 30000, // 30秒超时
    }),
  deleteSession: (sessionId) =>
    api.delete(`/optimization/sessions/${sessionId}`, {
      timeout: 10000, // 10秒超时
    }),
  retryFailedSegments: (sessionId) =>
    api.post(`/optimization/sessions/${sessionId}/retry`, null, {
      timeout: 15000, // 15秒超时
    }),
  getStreamUrl: (sessionId) => {
    const userToken = localStorage.getItem('userToken');
    const baseUrl = api.defaults.baseURL || '/api';
    const query = userToken ? `?access_token=${encodeURIComponent(userToken)}` : '';
    return `${baseUrl}/optimization/sessions/${sessionId}/stream${query}`;
  },
};

export default api;

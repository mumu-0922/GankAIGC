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
  listCreditTransactions: () => api.get('/user/credit-transactions'),
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

// Word Formatter API
export const wordFormatterAPI = {
  // Usage info (shared with polishing)
  getUsage: () => api.get('/word-formatter/usage'),

  // Built-in Specs
  listSpecs: () => api.get('/word-formatter/specs'),
  getSpecSchema: () => api.get('/word-formatter/specs/schema'),
  validateSpec: (specJson) =>
    api.post('/word-formatter/specs/validate', null, {
      params: { spec_json: specJson },
    }),
  generateSpec: (requirements, options = {}) =>
    api.post('/word-formatter/specs/generate', {
      requirements,
      billing_mode: options.billingMode || 'platform',
    }, {
      timeout: 120000, // AI generation may take time
    }),

  // Saved Specs (user's custom specs)
  saveSpec: (name, specJson, description = null) =>
    api.post('/word-formatter/specs/save', {
      name,
      spec_json: specJson,
      description,
    }),
  listSavedSpecs: () => api.get('/word-formatter/specs/saved'),
  getSavedSpec: (specId) => api.get(`/word-formatter/specs/saved/${specId}`),
  deleteSavedSpec: (specId) => api.delete(`/word-formatter/specs/saved/${specId}`),

  // Format text
  formatText: (data) =>
    api.post('/word-formatter/format/text', {
      ...data,
      billing_mode: data.billing_mode || data.billingMode || 'platform',
    }, {
      timeout: 60000,
    }),

  // Format file
  formatFile: (file, options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/word-formatter/format/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        ...options,
        billing_mode: options.billingMode || options.billing_mode || 'platform',
      },
      timeout: 120000,
    });
  },

  // Jobs
  getJobStatus: (jobId) => api.get(`/word-formatter/jobs/${jobId}`),
  listJobs: (limit = 10) =>
    api.get('/word-formatter/jobs', { params: { limit } }),
  deleteJob: (jobId) => api.delete(`/word-formatter/jobs/${jobId}`),
  getJobReport: (jobId) => api.get(`/word-formatter/jobs/${jobId}/report`),

  // Download
  getDownloadUrl: (jobId) => {
    const userToken = localStorage.getItem('userToken');
    const baseUrl = api.defaults.baseURL || '/api';
    const query = userToken ? `?access_token=${encodeURIComponent(userToken)}` : '';
    return `${baseUrl}/word-formatter/jobs/${jobId}/download${query}`;
  },

  // SSE stream URL
  getStreamUrl: (jobId) => {
    const userToken = localStorage.getItem('userToken');
    const baseUrl = api.defaults.baseURL || '/api';
    const query = userToken ? `?access_token=${encodeURIComponent(userToken)}` : '';
    return `${baseUrl}/word-formatter/jobs/${jobId}/stream${query}`;
  },

  // Preprocess text
  preprocessText: (text, options = {}) =>
    api.post('/word-formatter/preprocess/text', {
      text,
      chunk_paragraphs: options.chunkParagraphs || 40,
      chunk_chars: options.chunkChars || 8000,
      billing_mode: options.billingMode || 'platform',
    }, {
      timeout: 60000,
    }),

  // Preprocess file
  preprocessFile: (file, options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/word-formatter/preprocess/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        chunk_paragraphs: options.chunkParagraphs || 40,
        chunk_chars: options.chunkChars || 8000,
        billing_mode: options.billingMode || 'platform',
      },
      timeout: 120000,
    });
  },

  // Preprocess stream URL
  getPreprocessStreamUrl: (jobId) => {
    const userToken = localStorage.getItem('userToken');
    const baseUrl = api.defaults.baseURL || '/api';
    const query = userToken ? `?access_token=${encodeURIComponent(userToken)}` : '';
    return `${baseUrl}/word-formatter/preprocess/${jobId}/stream${query}`;
  },

  // Get preprocess result
  getPreprocessResult: (jobId) =>
    api.get(`/word-formatter/preprocess/${jobId}/result`),

  // Delete preprocess job
  deletePreprocessJob: (jobId) =>
    api.delete(`/word-formatter/preprocess/${jobId}`),

  // ============ Format Check API (No AI Required) ============

  // Get paragraph types
  getFormatParagraphTypes: () =>
    api.get('/word-formatter/format-check/types'),

  // Check text format (synchronous)
  checkTextFormat: (text, mode = 'loose') =>
    api.post('/word-formatter/format-check/text', { text, mode }, {
      timeout: 30000,
    }),

  // Check file format (synchronous)
  checkFileFormat: (file, mode = 'loose') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/word-formatter/format-check/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { mode },
      timeout: 60000,
    });
  },
};

export default api;

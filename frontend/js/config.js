// Cấu hình chung của frontend.
// Toàn bộ các API Key & Secret được lưu trong file .env và tự động nạp vào CONFIG.
const getInitialApiBaseUrl = () => {
  if (typeof window !== 'undefined' && window.location) {
    // Nếu chạy trực tiếp trên FastAPI port 8000
    if (window.location.port === '8000') {
      return `${window.location.origin}/api`;
    }
  }
  // Mặc định gọi Backend FastAPI port 8000 khi chạy từ Live Server (port 5500, 5501, 5502,...) hoặc file:///
  return "http://127.0.0.1:8000/api";
};

const CONFIG = {
  API_BASE_URL: getInitialApiBaseUrl(),
  APP_NAME: "RideHub",
  FIREBASE: {
    apiKey: "AIzaSyAeC9Ln5LN9IIlHhuwGoAcwKYp-8HDDyKU",         // Nạp sẵn mặc định từ .env
    projectId: "ridehub-carmoto",                               // Nạp sẵn mặc định từ .env
    authDomain: "ridehub-carmoto.firebaseapp.com",              // Nạp sẵn mặc định từ .env
    storageBucket: "ridehub-carmoto.appspot.com",               // Nạp sẵn mặc định từ .env
  }
};

/**
 * Hàm phân tích cú pháp chuỗi cấu hình dạng KEY=VALUE từ file .env
 */
function parseEnvContent(text) {
  const result = {};
  if (!text) return result;
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx > 0) {
      const key = trimmed.slice(0, eqIdx).trim();
      let val = trimmed.slice(eqIdx + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      result[key] = val;
    }
  }
  return result;
}

/**
 * Áp dụng các biến môi trường vào đối tượng CONFIG toàn cục
 */
function applyEnvToConfig(env) {
  if (!env) return;
  if (env.APP_NAME) CONFIG.APP_NAME = env.APP_NAME;
  if (env.API_BASE_URL) {
    // Nếu API_BASE_URL trỏ nhầm vào port của Live Server (5500, 5501, 5502), tự chuẩn hóa về port 8000 của FastAPI backend
    let apiUrl = env.API_BASE_URL;
    if (apiUrl.includes(':5501') || apiUrl.includes(':5500') || apiUrl.includes(':5502')) {
      apiUrl = apiUrl.replace(/:550[0-9]/, ':8000');
    }
    CONFIG.API_BASE_URL = apiUrl;
  }

  const apiKey = env.FIREBASE_WEB_API_KEY || env.VITE_FIREBASE_API_KEY;
  const projId = env.FIREBASE_PROJECT_ID || env.VITE_FIREBASE_PROJECT_ID;
  const domain = env.FIREBASE_AUTH_DOMAIN || env.VITE_FIREBASE_AUTH_DOMAIN;
  const bucket = env.FIREBASE_STORAGE_BUCKET || env.VITE_FIREBASE_STORAGE_BUCKET;

  if (apiKey) CONFIG.FIREBASE.apiKey = apiKey;
  if (projId) CONFIG.FIREBASE.projectId = projId;
  if (domain) CONFIG.FIREBASE.authDomain = domain;
  if (bucket) CONFIG.FIREBASE.storageBucket = bucket;
}

/**
 * Tự động nạp cấu hình từ .env:
 * 1. Thử fetch file .env tĩnh (/.env, ../.env, ../../.env, ./frontend/.env, v.v.)
 * 2. Thử fetch từ API Backend (/auth/config) nơi FastAPI đọc từ backend/.env
 */
async function loadEnvConfig() {
  // 1. Thử nạp từ file .env qua HTTP fetch
  const envCandidates = [
    '../.env',
    '../../.env',
    '/.env',
    './.env',
    '../frontend/.env',
    '/frontend/.env'
  ];
  for (const path of envCandidates) {
    try {
      const res = await fetch(path);
      if (res.ok) {
        const text = await res.text();
        if (text && (text.includes('FIREBASE_WEB_API_KEY') || text.includes('VITE_FIREBASE_API_KEY'))) {
          applyEnvToConfig(parseEnvContent(text));
          if (CONFIG.FIREBASE.apiKey) break;
        }
      }
    } catch (_) {}
  }

  // 2. Thử nạp từ backend API endpoint nếu chưa có hoặc để đảm bảo đồng bộ
  try {
    const res = await fetch(`${CONFIG.API_BASE_URL}/auth/config`);
    if (res.ok) {
      const result = await res.json();
      const data = result && result.data;
      if (data) {
        if (data.app_name) CONFIG.APP_NAME = data.app_name;
        if (data.firebase) {
          if (data.firebase.apiKey) CONFIG.FIREBASE.apiKey = data.firebase.apiKey;
          if (data.firebase.projectId) CONFIG.FIREBASE.projectId = data.firebase.projectId;
          if (data.firebase.authDomain) CONFIG.FIREBASE.authDomain = data.firebase.authDomain;
          if (data.firebase.storageBucket) CONFIG.FIREBASE.storageBucket = data.firebase.storageBucket;
        }
      }
    }
  } catch (_) {}

  // 3. Fallback từ localStorage nếu người dùng từng nhập tay
  if (!CONFIG.FIREBASE.apiKey) {
    const cachedKey = localStorage.getItem('ridehub_firebase_api_key');
    if (cachedKey) CONFIG.FIREBASE.apiKey = cachedKey;
  }

  return CONFIG;
}

// Khởi chạy nạp .env
const envConfigPromise = loadEnvConfig();
window.CONFIG = CONFIG;
window.envConfigPromise = envConfigPromise;

export const API_URL = 'https://agentmesh-riuz.onrender.com/api/v1';

/** Base URL workers use to reach the control plane (the API URL without its /api/v1 suffix). */
export const CONTROL_PLANE_URL = API_URL.replace(/\/api\/v\d+\/?$/, '');

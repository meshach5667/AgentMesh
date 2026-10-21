export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://agentmesh-riuz.onrender.com/api/v1';

export const CONTROL_PLANE_URL = API_URL.replace(/\/api\/v\d+\/?$/, '');

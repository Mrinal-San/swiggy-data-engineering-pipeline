import { api, queryString } from './client.js';

export const getDateRange = () => api('/dashboard/date-range');
export const getSummary = (range) => api(`/dashboard/summary?${queryString({ ...range, currency: 'INR' })}`);
export const getSalesTrend = (range) => api(`/dashboard/sales-trend?${queryString({ ...range, currency: 'INR', granularity: 'week' })}`);
export const getCities = (range) => api(`/dashboard/cities?${queryString({ ...range, currency: 'INR', limit: 10 })}`);
export const getCuisines = (range) => api(`/dashboard/cuisines?${queryString({ ...range, currency: 'INR', limit: 10 })}`);
export const getDeliveryAnalytics = () => api('/delivery/analytics');
export const refreshData = () => api('/dashboard/refresh', { method: 'POST' });

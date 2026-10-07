import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api', timeout: 30000 })

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    if (status === 401 && !location.pathname.includes('/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      location.href = '/login'
      return Promise.reject(err)
    }
    ElMessage.error(typeof detail === 'string' ? detail : (err.message || '请求失败'))
    return Promise.reject(err)
  }
)

export default api

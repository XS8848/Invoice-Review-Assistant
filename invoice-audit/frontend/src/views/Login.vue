<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>发票审计系统</h2>
      <el-form :model="form" @submit.prevent>
        <el-form-item>
          <el-input v-model="form.emp_no" placeholder="员工工号（审查员为 admin）" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="doLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="doLogin">登 录</el-button>
      </el-form>
      <div class="links">
        <el-link type="primary" @click="regVisible = true">员工注册</el-link>
        <el-link type="info" @click="pwdVisible = true">修改密码</el-link>
      </div>
    </el-card>

    <!-- 员工注册 -->
    <el-dialog v-model="regVisible" title="员工注册" width="480px">
      <el-form :model="reg" label-width="80px">
        <el-form-item label="员工工号"><el-input v-model="reg.emp_no" placeholder="8位字母或数字" maxlength="8" /></el-form-item>
        <el-form-item label="员工名字"><el-input v-model="reg.name" /></el-form-item>
        <el-form-item label="员工部门">
          <el-select v-model="reg.department" placeholder="请选择" style="width: 100%">
            <el-option v-for="d in enums.departments" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="员工职级">
          <el-select v-model="reg.job_level" placeholder="请选择" style="width: 100%">
            <el-option v-for="d in enums.job_levels" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="员工岗位">
          <el-select v-model="reg.position" placeholder="请选择" style="width: 100%">
            <el-option v-for="d in enums.positions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="员工密码"><el-input v-model="reg.password" type="password" show-password placeholder="至少6位" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="regVisible = false">取消</el-button>
        <el-button type="primary" :loading="regLoading" @click="doRegister">注册</el-button>
      </template>
    </el-dialog>

    <!-- 修改密码 -->
    <el-dialog v-model="pwdVisible" title="修改密码" width="420px">
      <el-form :model="pwd" label-width="80px">
        <el-form-item label="员工工号"><el-input v-model="pwd.emp_no" placeholder="审查员为 admin" /></el-form-item>
        <el-form-item label="原始密码"><el-input v-model="pwd.old_password" type="password" show-password /></el-form-item>
        <el-form-item label="新密码"><el-input v-model="pwd.new_password" type="password" show-password placeholder="至少6位" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="doChangePwd">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const form = reactive({ emp_no: '', password: '' })
const loading = ref(false)
const regVisible = ref(false)
const pwdVisible = ref(false)
const regLoading = ref(false)
const pwdLoading = ref(false)
const enums = reactive({ departments: [], job_levels: [], positions: [] })
const reg = reactive({ emp_no: '', name: '', department: '', job_level: '', position: '', password: '' })
const pwd = reactive({ emp_no: '', old_password: '', new_password: '' })

onMounted(async () => {
  try { Object.assign(enums, await api.get('/enums')) } catch (e) { /* 后端未启动时忽略 */ }
})

async function doLogin() {
  loading.value = true
  try {
    const res = await api.post('/auth/login', form)
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
    if (res.user.must_change_password) ElMessage.warning('首次登录请尽快修改密码')
    router.push(res.user.role === 'admin' ? '/home/reviewer' : '/home/employee')
  } catch (e) {} finally { loading.value = false }
}

async function doRegister() {
  if (!/^[A-Za-z0-9]{8}$/.test(reg.emp_no)) return ElMessage.warning('员工工号必须是8位字母或数字')
  regLoading.value = true
  try {
    await api.post('/auth/register', reg)
    ElMessage.success('注册成功，请登录')
    regVisible.value = false
    Object.assign(reg, { emp_no: '', name: '', department: '', job_level: '', position: '', password: '' })
  } catch (e) {} finally { regLoading.value = false }
}

async function doChangePwd() {
  pwdLoading.value = true
  try {
    await api.post('/auth/change-password', pwd)
    ElMessage.success('密码已修改')
    pwdVisible.value = false
  } catch (e) {} finally { pwdLoading.value = false }
}
</script>

<style scoped>
.login-wrap { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1f6feb 0%, #6f42c1 100%); }
.login-card { width: 400px; padding: 12px; }
.login-card h2 { text-align: center; color: #333; margin-bottom: 20px; }
.links { display: flex; justify-content: space-between; margin-top: 12px; }
</style>

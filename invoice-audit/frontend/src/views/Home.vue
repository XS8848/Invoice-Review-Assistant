<template>
  <el-container style="height: 100vh">
    <el-header class="header">
      <div class="title">📋 发票审计系统</div>
      <div class="right">
        <span class="who">{{ user?.name }}（{{ user?.emp_no }}）{{ user?.role === 'admin' ? '[审查员]' : `[${user?.department}/${user?.position}]` }}</span>
        <el-button v-if="user?.role === 'admin'" size="small" @click="go('reviewer')">审查工作台</el-button>
        <el-button v-if="user?.role === 'admin'" size="small" @click="go('config')">模型调参</el-button>
        <el-button v-if="user?.role === 'admin'" size="small" @click="go('monitor')">系统状态</el-button>
        <el-button v-if="user?.role === 'admin'" size="small" @click="go('dashboard')">数据看板</el-button>
        <el-button size="small" type="danger" plain @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main style="padding: 0; overflow: hidden">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || 'null') } catch (e) { return null }
})

function go(path) { router.push(`/home/${path}`) }
function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  location.href = '/login'
}
</script>

<style scoped>
.header { background: #1f2d3d; color: #fff; display: flex; align-items: center; justify-content: space-between; }
.title { font-size: 18px; font-weight: 600; }
.who { margin-right: 12px; color: #c0c9d4; }
</style>

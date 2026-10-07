<template>
  <div class="page">
    <h3>📈 系统状态监控 <span class="tip">每 3 秒刷新</span></h3>
    <el-row :gutter="16" v-if="mon">
      <el-col :span="4"><el-card shadow="never"><div class="m-title">CPU</div><div class="m-big">{{ mon.cpu.percent }}%</div><div class="m-sub">{{ mon.cpu.count }} 核</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="m-title">内存</div><div class="m-big">{{ mon.memory.percent }}%</div><div class="m-sub">{{ mon.memory.used_mb }} / {{ mon.memory.total_mb }} MB</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="m-title">磁盘</div><div class="m-big">{{ mon.disk.percent }}%</div><div class="m-sub">{{ mon.disk.used_gb }} / {{ mon.disk.total_gb }} GB</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="m-title">GPU</div><div class="m-big">{{ mon.gpu.available ? mon.gpu.util + '%' : 'N/A' }}</div><div class="m-sub" v-if="mon.gpu.available">显存 {{ mon.gpu.mem_used_mb }}/{{ mon.gpu.mem_total_mb }}MB · {{ mon.gpu.temp_c }}°C</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="m-title">数据库</div><div class="m-big"><el-tag :type="mon.database.status === 'ok' ? 'success' : 'danger'">{{ mon.database.status }}</el-tag></div><div class="m-sub">{{ mon.database.url }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="m-title">MinIO</div><div class="m-big"><el-tag :type="mon.minio.healthy ? 'success' : 'danger'">{{ mon.minio.healthy ? '正常' : '异常' }}</el-tag></div><div class="m-sub">{{ mon.minio.endpoint }}</div></el-card></el-col>
    </el-row>
    <el-empty v-else description="无法获取监控数据" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import api from '../api'

const mon = ref(null)
let timer = null

async function refresh() {
  try { mon.value = await api.get('/monitor') } catch (e) {}
}
onMounted(() => { refresh(); timer = setInterval(refresh, 3000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.page { padding: 16px; background: #f0f2f5; height: 100%; overflow-y: auto; box-sizing: border-box; }
.page h3 { margin: 0 0 14px; }
.tip { color: #909399; font-size: 12px; margin-left: 10px; font-weight: normal; }
.m-title { font-size: 13px; color: #606266; }
.m-big { font-size: 26px; font-weight: 600; margin: 8px 0; }
.m-sub { font-size: 11px; color: #909399; }
</style>

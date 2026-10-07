<template>
  <el-container style="height: 100%">
    <!-- 左：待人工审查队列 -->
    <el-aside width="330px" class="aside">
      <div class="aside-title">待人工审查队列 <el-badge :value="queue.length" type="warning" /></div>
      <el-scrollbar height="calc(100vh - 120px)">
        <div v-for="c in queue" :key="c.id" class="q-item" :class="{ active: current?.id === c.id }" @click="select(c)">
          <div class="q-top">
            <span class="q-name">{{ c.emp_name }}（{{ c.emp_no }}）</span>
            <el-tag size="small" :type="excTag(c.exception_type).type">{{ excTag(c.exception_type).text }}</el-tag>
          </div>
          <div class="q-sub">{{ c.file_name }}</div>
          <div class="q-sub">{{ c.department }} / {{ c.job_level }} / {{ c.position }} · {{ fmt(c.submitted_at) }}</div>
        </div>
        <el-empty v-if="!queue.length" description="队列为空" />
      </el-scrollbar>
    </el-aside>

    <!-- 中：工作区 -->
    <el-main class="work">
      <el-card v-if="current" shadow="never">
        <template #header><b>审查工作区</b></template>
        <div class="work-grid">
          <div class="file-pane">
            <img v-if="fileUrl && current.file_type !== 'pdf'" :src="fileUrl" class="invoice-img" alt="发票" />
            <iframe v-else-if="fileUrl" :src="fileUrl" class="invoice-frame"></iframe>
            <el-empty v-else description="原图加载中…" :image-size="60" />
            <el-button size="small" style="margin-top: 8px" @click="openFile">新窗口打开原图</el-button>
          </div>
          <div class="info-pane">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="员工工号">{{ current.emp_no }}</el-descriptions-item>
              <el-descriptions-item label="员工名字">{{ current.emp_name }}</el-descriptions-item>
              <el-descriptions-item label="员工职级">{{ current.job_level }}</el-descriptions-item>
              <el-descriptions-item label="员工岗位">{{ current.position }}</el-descriptions-item>
              <el-descriptions-item label="员工部门">{{ current.department }}</el-descriptions-item>
              <el-descriptions-item label="上传时间">{{ fmt(current.submitted_at) }}</el-descriptions-item>
              <el-descriptions-item label="模型状态码">流程{{ current.flow_status }} / 异常{{ current.exception_type }} / 队列{{ current.queue_state }}</el-descriptions-item>
              <el-descriptions-item label="识别置信度">{{ current.ocr_conf ?? '—' }}</el-descriptions-item>
              <el-descriptions-item label="批次号" :span="2">{{ current.batch_id }}</el-descriptions-item>
            </el-descriptions>

            <div v-if="siblings.length" style="margin-top: 10px">
              <b style="font-size: 13px">同批次其他文件（{{ siblings.length }}）</b>
              <div v-for="s in siblings" :key="s.id" class="sib">
                <span class="sib-name">{{ s.file_name }}</span>
                <el-tag size="small" :type="s.reimb_result === 0 ? 'success' : s.reimb_result === 1 ? 'danger' : 'info'">
                  {{ s.reimb_result === 0 ? '报销' : s.reimb_result === 1 ? '不报销' : flowShort(s) }}
                </el-tag>
                <el-button size="small" link type="primary" @click="openSiblingFile(s)">查看</el-button>
              </div>
            </div>

            <el-alert type="warning" :closable="false" style="margin-top: 10px" :title="'模型返回信息：' + (current.model_note || '无')" />

            <div v-if="current.ocr_text" style="margin-top: 10px">
              <el-collapse>
                <el-collapse-item title="发票识别字段">
                  <pre class="json">{{ JSON.stringify(current.ocr_text, null, 2) }}</pre>
                </el-collapse-item>
                <el-collapse-item v-if="current.rule_check" title="规则引擎结论">
                  <pre class="json">{{ JSON.stringify(current.rule_check, null, 2) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>

            <el-input v-model="reviewNote" type="textarea" :rows="2" placeholder="发送给员工的备注信息（可写可不写）" style="margin-top: 10px" />
            <div style="margin-top: 12px; display: flex; gap: 12px">
              <el-button type="success" size="large" style="flex: 1" :loading="submitting" @click="judge(0)">✔ 报销</el-button>
              <el-button type="danger" size="large" style="flex: 1" :loading="submitting" @click="judge(1)">✘ 不报销</el-button>
            </div>
          </div>
        </div>
      </el-card>
      <el-empty v-else description="点击左侧队列选择单据" />
    </el-main>

    <!-- 右：系统状态 -->
    <el-aside width="300px" class="aside">
      <div class="aside-title">系统状态 <el-link type="primary" style="float: right" @click="$router.push('/home/monitor')">详情</el-link></div>
      <template v-if="mon">
        <div class="m-row"><span>CPU</span><el-progress :percentage="mon.cpu.percent" :stroke-width="8" /></div>
        <div class="m-row"><span>内存</span><el-progress :percentage="mon.memory.percent" :stroke-width="8" /></div>
        <div class="m-row"><span>磁盘</span><el-progress :percentage="mon.disk.percent" :stroke-width="8" /></div>
        <div class="m-row" v-if="mon.gpu.available"><span>GPU</span><el-progress :percentage="mon.gpu.util" :stroke-width="8" />
          <span class="m-sub">{{ mon.gpu.name }} · 显存 {{ mon.gpu.mem_used_mb }}MB/{{ mon.gpu.mem_total_mb }}MB · {{ mon.gpu.temp_c }}°C</span>
        </div>
        <div class="m-row"><span>数据库</span><el-tag size="small" :type="mon.database.status === 'ok' ? 'success' : 'danger'">{{ mon.database.status }}</el-tag></div>
        <div class="m-row"><span>MinIO</span><el-tag size="small" :type="mon.minio.healthy ? 'success' : 'danger'">{{ mon.minio.healthy ? '正常' : '异常' }}</el-tag></div>
      </template>
      <div style="margin-top: 16px">
        <el-button type="primary" style="width: 100%" @click="$router.push('/home/dashboard')">📊 数据看板</el-button>
        <el-button style="width: 100%; margin: 8px 0 0" @click="$router.push('/home/config')">⚙️ 模型调参界面</el-button>
      </div>
    </el-aside>
  </el-container>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const queue = ref([])
const current = ref(null)
const siblings = ref([])
const fileUrl = ref('')
const reviewNote = ref('')
const submitting = ref(false)
const mon = ref(null)
let timer = null

async function refresh() {
  try {
    const q = await api.get('/review/queue')
    queue.value = q
    if (current.value) {
      const fresh = q.find((x) => x.id === current.value.id)
      current.value = fresh || null
    }
    if (!current.value && q.length) current.value = q[0]
    await loadSiblings()
  } catch (e) {}
}

async function loadSiblings() {
  siblings.value = []
  if (!current.value) return
  try {
    const all = await api.get(`/claims/batch/${current.value.batch_id}`)
    siblings.value = all.filter((x) => x.id !== current.value.id)
  } catch (e) {}
}

// 修复：通过 axios（携带 JWT）先取预签名 URL 再展示，避免 <img>/<iframe> 直连被 401
async function loadFile() {
  fileUrl.value = ''
  if (!current.value) return
  try {
    const r = await api.get(`/claims/${current.value.id}/file`)
    fileUrl.value = r.url
  } catch (e) {}
}

async function refreshMon() {
  try { mon.value = await api.get('/monitor') } catch (e) {}
}

function select(c) {
  current.value = c
  loadSiblings()
  loadFile()
}

async function openFile() {
  if (!current.value) return
  try {
    const r = await api.get(`/claims/${current.value.id}/file`)
    window.open(r.url, '_blank')
  } catch (e) {}
}

async function openSiblingFile(s) {
  try {
    const r = await api.get(`/claims/${s.id}/file`)
    window.open(r.url, '_blank')
  } catch (e) {}
}

function flowShort(c) {
  if (c.flow_status === 0) return '已处理'
  if (c.flow_status === 3) return '待人工'
  return '处理中'
}

async function judge(result) {
  if (!current.value) return
  submitting.value = true
  try {
    await api.post(`/review/${current.value.id}`, { result, note: reviewNote.value })
    ElMessage.success(result === 0 ? '已判定：报销' : '已判定：不报销')
    reviewNote.value = ''
    current.value = null
    fileUrl.value = ''
    await refresh()
  } catch (e) {} finally { submitting.value = false }
}

function excTag(t) {
  if (t === 1) return { type: 'warning', text: '视觉置信度低' }
  if (t === 2) return { type: 'info', text: 'LLM无法判断' }
  if (t === 3) return { type: 'danger', text: '系统故障' }
  return { type: 'info', text: '待人工' }
}
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 19) : '' }

onMounted(() => {
  refresh()
  loadFile()
  refreshMon()
  timer = setInterval(() => { refresh(); refreshMon() }, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.aside { border-right: 1px solid #e4e7ed; background: #fff; padding: 12px; }
.aside-title { font-weight: 600; margin-bottom: 8px; }
.q-item { padding: 10px; border-radius: 6px; cursor: pointer; margin-bottom: 6px; background: #f7f9fc; }
.q-item.active { background: #e6f4ff; outline: 1px solid #91caff; }
.q-top { display: flex; justify-content: space-between; align-items: center; }
.q-name { font-size: 13px; font-weight: 600; }
.q-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.work { background: #f0f2f5; padding: 16px; overflow: auto; }
.work-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.file-pane { display: flex; flex-direction: column; align-items: center; }
.invoice-img { max-width: 100%; max-height: 70vh; border: 1px solid #e4e7ed; border-radius: 4px; }
.invoice-frame { width: 100%; height: 70vh; border: 1px solid #e4e7ed; border-radius: 4px; }
.m-row { margin-bottom: 10px; font-size: 13px; }
.m-sub { font-size: 11px; color: #909399; }
.sib { display: flex; align-items: center; gap: 8px; padding: 4px 0; border-bottom: 1px dashed #ebeef5; font-size: 12px; }
.sib-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.json { background: #f6f8fa; padding: 10px; border-radius: 4px; font-size: 12px; overflow: auto; max-height: 300px; }
</style>

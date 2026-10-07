<template>
  <el-container style="height: 100%">
    <!-- 左侧：历史报销记录（按批次聚合） -->
    <el-aside width="360px" class="aside">
      <div class="aside-title">我的历史报销记录</div>
      <el-scrollbar height="calc(100vh - 120px)">
        <template v-if="batches.length">
          <el-collapse v-model="openBatches">
            <el-collapse-item v-for="b in batches" :key="b.id" :name="b.id">
              <template #title>
                <div class="batch-head">
                  <el-tag size="small" :type="batchTag(b).type">{{ batchTag(b).text }}</el-tag>
                  <span class="batch-sub">批次 {{ b.id.slice(0, 8) }} · {{ b.items.length }} 个文件 · {{ fmt(b.submitted_at) }}</span>
                </div>
              </template>
              <div v-for="c in b.items" :key="c.id" class="rec-item" :class="{ active: current?.id === c.id }" @click.stop="current = c">
                <div class="rec-top">
                  <span class="fname">{{ c.file_name }}</span>
                  <el-tag size="small" :type="resultTag(c).type">{{ resultTag(c).text }}</el-tag>
                </div>
                <div class="rec-sub">¥{{ c.ocr_text?.total_amount || '-' }} · 置信度 {{ c.ocr_conf ?? '-' }}</div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-empty v-else description="暂无报销记录" />
      </el-scrollbar>
    </el-aside>

    <el-main class="main">
      <!-- 上传区 -->
      <el-card shadow="never" style="margin-bottom: 12px">
        <template #header><b>提交报销表单</b><span class="tip">（支持 PDF / JPG / PNG，单次最多 20 个；同一次提交 = 一个批次）</span></template>
        <el-upload
          drag multiple :auto-upload="false" :limit="20" accept=".jpg,.jpeg,.png,.pdf"
          v-model:file-list="fileList" style="width: 100%"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">将发票拖到此处，或<em>点击选择文件</em></div>
        </el-upload>
        <el-input v-model="note" type="textarea" :rows="2" placeholder="报销备注（可写可不写；餐饮/住宿等敏感品类建议填写事由）" style="margin-top: 10px" />
        <el-button type="primary" style="margin-top: 10px" :loading="uploading" @click="doUpload">确认提交</el-button>
      </el-card>

      <!-- 进度详情 -->
      <el-card v-if="current" shadow="never">
        <template #header>
          <b>报销单 #{{ current.id }} · {{ current.file_name }}</b>
          <span class="tip">批次 {{ current.batch_id.slice(0, 8) }}</span>
          <el-button size="small" style="float: right" @click="viewFile(current)">查看原图</el-button>
        </template>

        <el-steps :active="stepOf(current)" align-center style="margin-bottom: 16px">
          <el-step title="已提交" />
          <el-step title="视觉识别" />
          <el-step title="语言模型审查" />
          <el-step title="人工审查" />
          <el-step title="完成" />
        </el-steps>

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="流程状态">{{ flowText(current) }}</el-descriptions-item>
          <el-descriptions-item label="报销结果">
            <el-tag :type="current.reimb_result === 0 ? 'success' : current.reimb_result === 1 ? 'danger' : 'info'">
              {{ current.reimb_result === 0 ? '报销' : current.reimb_result === 1 ? '不报销' : '处理中' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模型返回备注">{{ current.model_note || '—' }}</el-descriptions-item>
          <el-descriptions-item label="审查员返回备注">{{ current.reviewer_note || '—' }}</el-descriptions-item>
          <el-descriptions-item label="我的备注">{{ current.user_note || '—' }}</el-descriptions-item>
          <el-descriptions-item label="识别置信度">{{ current.ocr_conf ?? '—' }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse style="margin-top: 10px" v-if="current.ocr_text">
          <el-collapse-item title="发票识别字段（点击展开）">
            <pre class="json">{{ JSON.stringify(current.ocr_text, null, 2) }}</pre>
          </el-collapse-item>
          <el-collapse-item v-if="current.rule_check" title="规则引擎结论（点击展开）">
            <pre class="json">{{ JSON.stringify(current.rule_check, null, 2) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import api from '../api'

const claims = ref([])
const current = ref(null)
const fileList = ref([])
const note = ref('')
const uploading = ref(false)
const openBatches = ref([])
let timer = null

const batches = computed(() => {
  const map = new Map()
  for (const c of claims.value) {
    if (!map.has(c.batch_id)) map.set(c.batch_id, [])
    map.get(c.batch_id).push(c)
  }
  return [...map.entries()].map(([id, items]) => ({
    id, items,
    submitted_at: items[0].submitted_at,
    done: items.every((x) => x.flow_status === 0),
    approved: items.filter((x) => x.reimb_result === 0).length,
    rejected: items.filter((x) => x.reimb_result === 1).length,
  }))
})

function batchTag(b) {
  if (b.done) return { type: 'info', text: `完成 ${b.approved}报销/${b.rejected}不报销` }
  return { type: 'warning', text: '处理中' }
}

async function refresh() {
  try {
    const list = await api.get('/claims/mine')
    claims.value = list
    if (!current.value && list.length) current.value = list[0]
    else if (current.value) {
      const fresh = list.find((x) => x.id === current.value.id)
      if (fresh) current.value = fresh
    }
  } catch (e) {}
}

function flowText(c) {
  if (c.flow_status === 0) return '已处理'
  if (c.flow_status === 1) return c.queue_state === 0 ? '视觉识别中' : '排队中（已提交）'
  if (c.flow_status === 2) return c.queue_state === 0 ? '语言模型审查中' : '等待语言模型审查'
  if (c.flow_status === 3) return '待人工审查'
  if (c.flow_status === 4) return '系统异常'
  return '-'
}

function stepOf(c) {
  if (c.flow_status === 1) return c.queue_state === 0 ? 1 : 0
  if (c.flow_status === 2) return c.queue_state === 0 ? 2 : 1
  if (c.flow_status === 3) return 3
  return 4
}

function resultTag(c) {
  if (c.flow_status !== 0) return { type: 'info', text: flowText(c) }
  return c.reimb_result === 0 ? { type: 'success', text: '已报销' } : { type: 'danger', text: '不报销' }
}

function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 19) : '' }

async function doUpload() {
  if (!fileList.value.length) return ElMessage.warning('请先选择文件')
  uploading.value = true
  try {
    const fd = new FormData()
    fileList.value.forEach((f) => fd.append('files', f.raw))
    fd.append('note', note.value)
    const created = await api.post('/claims', fd)
    ElMessage.success(`已提交 ${created.length} 个文件（同一批次），进入审核流程`)
    fileList.value = []
    note.value = ''
    await refresh()
    current.value = created[0]
    openBatches.value = [created[0].batch_id]
  } catch (e) {} finally { uploading.value = false }
}

// 修复：通过 axios（携带 JWT）先取预签名 URL 再打开，避免 <img>/<iframe> 直连被 401
async function viewFile(c) {
  try {
    const r = await api.get(`/claims/${c.id}/file`)
    window.open(r.url, '_blank')
  } catch (e) {}
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.aside { border-right: 1px solid #e4e7ed; background: #fff; padding: 12px; }
.aside-title { font-weight: 600; margin-bottom: 8px; }
.batch-head { display: flex; align-items: center; gap: 8px; width: 100%; }
.batch-sub { font-size: 12px; color: #909399; }
.rec-item { padding: 10px; border-radius: 6px; cursor: pointer; margin-bottom: 6px; background: #f7f9fc; }
.rec-item.active { background: #e6f4ff; outline: 1px solid #91caff; }
.rec-top { display: flex; justify-content: space-between; align-items: center; }
.fname { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 190px; }
.rec-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.main { background: #f0f2f5; padding: 16px; overflow: auto; }
.tip { color: #909399; font-size: 12px; margin-left: 10px; font-weight: normal; }
.json { background: #f6f8fa; padding: 10px; border-radius: 4px; font-size: 12px; overflow: auto; max-height: 300px; }
</style>

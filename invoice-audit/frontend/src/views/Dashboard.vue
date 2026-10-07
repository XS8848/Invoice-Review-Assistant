<template>
  <div class="page">
    <h3>📊 数据看板 <span class="tip">全部报销单 · 历史结果可修正（操作写入审计日志）</span></h3>

    <el-row :gutter="16" style="margin-bottom: 12px">
      <el-col :span="4"><el-card shadow="never"><div class="s-title">报销单总数</div><div class="s-big">{{ stats.total }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="s-title">已报销</div><div class="s-big" style="color:#67c23a">{{ stats.by_result[0] || 0 }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="s-title">不报销</div><div class="s-big" style="color:#f56c6c">{{ stats.by_result[1] || 0 }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="s-title">处理中</div><div class="s-big" style="color:#909399">{{ stats.by_result[2] || 0 }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="s-title">待人工审查</div><div class="s-big" style="color:#e6a23c">{{ stats.by_flow[3] || 0 }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="s-title">注册员工</div><div class="s-big">{{ stats.users }}</div></el-card></el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <b>报销单全表</b>
        <el-select v-model="filterFlow" placeholder="流程状态" clearable size="small" style="width: 140px; margin-left: 10px" @change="load">
          <el-option label="已处理(0)" :value="0" /><el-option label="待处理(1)" :value="1" />
          <el-option label="视觉已处理(2)" :value="2" /><el-option label="待人工审查(3)" :value="3" /><el-option label="失败(4)" :value="4" />
        </el-select>
        <el-select v-model="filterResult" placeholder="报销结果" clearable size="small" style="width: 140px; margin-left: 6px" @change="load">
          <el-option label="报销(0)" :value="0" /><el-option label="不报销(1)" :value="1" /><el-option label="处理中(2)" :value="2" />
        </el-select>
      </template>
      <el-table :data="items" size="small" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="emp_no" label="工号" width="100" />
        <el-table-column prop="emp_name" label="姓名" width="90" />
        <el-table-column prop="file_name" label="文件" min-width="150" show-overflow-tooltip />
        <el-table-column label="流程" width="90">
          <template #default="{ row }">{{ flowText(row.flow_status) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-select :model-value="row.reimb_result" size="small" @change="(v) => edit(row, 'reimb_result', v)">
              <el-option label="报销" :value="0" /><el-option label="不报销" :value="1" /><el-option label="处理中" :value="2" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column prop="model_note" label="模型备注" min-width="160" show-overflow-tooltip />
        <el-table-column prop="reviewer_note" label="审查员备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ fmt(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewFile(row)">原图</el-button>
            <el-button
              v-if="row.flow_status !== 1 && row.flow_status !== 2"
              size="small" link type="warning"
              @click="requeue(row)"
            >重新派发</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top: 10px" background layout="prev, pager, next, total"
        :total="total" :page-size="pageSize" :current-page="page" @current-change="(p) => { page = p; load() }"
      />
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>数据库表清单（点击"查看数据"浏览全表，含密码表）</b></template>
          <el-table :data="tables" size="small">
            <el-table-column prop="table" label="表名" />
            <el-table-column prop="rows" label="行数" width="100" />
            <el-table-column label="字段" min-width="180">
              <template #default="{ row }"><span class="cols">{{ row.columns.join(', ') }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="110">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openTable(row)">查看数据</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>审计日志（最近50条）</b></template>
          <el-table :data="logs" size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="operator" label="操作人" width="90" />
            <el-table-column prop="action" label="动作" width="120" />
            <el-table-column prop="table_name" label="表" width="80" />
            <el-table-column prop="row_id" label="行" width="60" />
            <el-table-column label="时间" width="160">
              <template #default="{ row }">{{ fmt(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 表数据浏览弹窗（密码表 users 等全表数据） -->
    <el-dialog v-model="tableDialog" :title="`表数据：${tableName}`" width="80%" top="6vh">
      <div class="td-bar">
        <span class="td-total">共 {{ tableTotal }} 行</span>
        <el-pagination
          background layout="prev, pager, next" small
          :total="tableTotal" :page-size="tablePageSize" :current-page="tablePage"
          @current-change="(p) => { tablePage = p; loadTableData() }"
        />
      </div>
      <el-table :data="tableRows" size="small" border max-height="60vh">
        <el-table-column v-for="col in tableCols" :key="col" :prop="col" :label="col" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="cell-val">{{ fmtVal(row[col]) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const items = ref([])
const stats = ref({ total: 0, by_flow: {}, by_result: {}, users: 0 })
const tables = ref([])
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filterFlow = ref(null)
const filterResult = ref(null)

// 表数据浏览
const tableDialog = ref(false)
const tableName = ref('')
const tableCols = ref([])
const tableRows = ref([])
const tableTotal = ref(0)
const tablePage = ref(1)
const tablePageSize = 20

function flowText(f) {
  return { 0: '已处理', 1: '待处理', 2: '视觉已处理', 3: '待人工审查', 4: '失败' }[f] || f
}
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 19) : '' }
function fmtVal(v) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

async function load() {
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filterFlow.value !== null && filterFlow.value !== '') params.flow_status = filterFlow.value
    if (filterResult.value !== null && filterResult.value !== '') params.reimb_result = filterResult.value
    const res = await api.get('/dashboard/claims', { params })
    items.value = res.items
    total.value = res.total
    stats.value = await api.get('/dashboard/stats')
    tables.value = await api.get('/dashboard/tables')
    logs.value = await api.get('/dashboard/audit-logs')
  } catch (e) {}
}

async function edit(row, field, value) {
  try {
    await api.put(`/dashboard/claims/${row.id}`, { [field]: value })
    ElMessage.success('已修正，审计日志已记录')
    row[field] = value
    await load()
  } catch (e) {}
}

async function requeue(row) {
  try {
    await ElMessageBox.confirm(`确认把 #${row.id}（${row.file_name}）重新派发到视觉识别流程？`, '重新派发', { type: 'warning' })
    await api.put(`/dashboard/claims/${row.id}/requeue`)
    ElMessage.success('已重新派发，状态机将自动处理')
    await load()
  } catch (e) {}
}

async function viewFile(row) {
  try {
    const r = await api.get(`/claims/${row.id}/file`)
    window.open(r.url, '_blank')
  } catch (e) {}
}

async function openTable(row) {
  tableName.value = row.table
  tablePage.value = 1
  tableDialog.value = true
  await loadTableData()
}

async function loadTableData() {
  try {
    const r = await api.get(`/dashboard/table/${tableName.value}`, {
      params: { page: tablePage.value, page_size: tablePageSize },
    })
    tableCols.value = r.columns
    tableRows.value = r.rows
    tableTotal.value = r.total
  } catch (e) {}
}

onMounted(load)
</script>

<style scoped>
.page { padding: 16px; background: #f0f2f5; height: 100%; overflow-y: auto; box-sizing: border-box; }
.page h3 { margin: 0 0 14px; }
.tip { color: #909399; font-size: 12px; margin-left: 10px; font-weight: normal; }
.s-title { font-size: 13px; color: #606266; }
.s-big { font-size: 26px; font-weight: 600; margin-top: 6px; }
.cols { font-size: 11px; color: #909399; }
.cell-val { font-size: 12px; word-break: break-all; }
.td-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.td-total { font-size: 13px; color: #606266; }
</style>

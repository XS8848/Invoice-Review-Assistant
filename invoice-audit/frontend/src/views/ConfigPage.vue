<template>
  <div class="page">
    <h3>⚙️ 模型调参界面 <span class="tip">修改后即时生效（写入数据库配置表）</span></h3>
    <el-row :gutter="16">
      <!-- 视觉模型 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>视觉模型配置（PaddleOCR / PP-StructureV3）</b></template>
          <el-form label-width="140px" size="small">
            <el-form-item label="设备 device">
              <el-select v-model="vision.device" style="width: 100%">
                <el-option label="GPU (gpu:0)" value="gpu:0" />
                <el-option label="CPU (cpu)" value="cpu" />
              </el-select>
            </el-form-item>
            <el-form-item label="置信度阈值">
              <el-input-number v-model="vision.conf_threshold" :min="0" :max="1" :step="0.05" />
              <span class="tip2">聚合置信度低于阈值 → 打回人工审查</span>
            </el-form-item>
            <el-form-item label="聚合权重[平均,最低]">
              <el-input v-model="vision.agg_weights_text" placeholder="0.6,0.4" />
            </el-form-item>
            <el-form-item label="图片最大边长">
              <el-input-number v-model="vision.max_side" :min="800" :max="4000" :step="200" />
              <span class="tip2">超过自动缩放（防 GPU OOM）</span>
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="saving" @click="save('vision')">保存视觉配置</el-button>
        </el-card>
      </el-col>

      <!-- 语言模型 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>语言模型配置（DeepSeek）</b></template>
          <el-form label-width="140px" size="small">
            <el-form-item label="模型名">
              <el-input v-model="llm.model" placeholder="deepseek-flash" />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="llm.base_url" placeholder="https://api.deepseek.com/v1" />
            </el-form-item>
            <el-form-item label="温度 temperature">
              <el-input-number v-model="llm.temperature" :min="0" :max="1.5" :step="0.1" />
            </el-form-item>
            <el-form-item label="超时(秒)">
              <el-input-number v-model="llm.timeout_seconds" :min="10" :max="600" />
            </el-form-item>
            <el-form-item label="系统提示词">
              <el-input v-model="llm.system_prompt" type="textarea" :rows="8" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="saving" @click="save('llm')">保存语言配置</el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 报销规则 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>报销规则（公司报销制度）</b></template>
          <el-form label-width="160px" size="small">
            <el-form-item label="公司名称">
              <el-input v-model="rules.company_name" placeholder="抬头校验基准名称" />
            </el-form-item>
            <el-form-item label="公司税号">
              <el-input v-model="rules.company_tax_id" placeholder="抬头校验基准税号" />
            </el-form-item>
            <el-form-item label="发票有效期(天)">
              <el-input-number v-model="rules.max_age_days" :min="1" :max="3650" />
            </el-form-item>
            <el-form-item label="单笔金额上限">
              <el-input-number v-model="rules.per_claim_limit" :min="0" :step="500" />
              <span class="tip2">超出转人工</span>
            </el-form-item>
            <el-form-item label="每人月累计上限">
              <el-input-number v-model="rules.per_month_limit" :min="0" :step="1000" />
            </el-form-item>
            <el-form-item label="敏感品类">
              <el-input v-model="rules.sensitive_text" placeholder="逗号分隔，如：餐饮,烟,酒" />
            </el-form-item>
            <el-form-item label="允许税率">
              <el-input v-model="rules.tax_rates_text" placeholder="逗号分隔，如：1%,3%,6%" />
            </el-form-item>
            <el-form-item label="规则开关">
              <el-checkbox v-model="rules.deduplicate_no">重复发票号检测</el-checkbox>
              <el-checkbox v-model="rules.check_arithmetic">金额算术校验</el-checkbox>
              <el-checkbox v-model="rules.require_buyer_match">抬头校验</el-checkbox>
              <el-checkbox v-model="rules.hard_fail_skips_llm">硬规则不过跳过LLM</el-checkbox>
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="saving" @click="save('rules')">保存报销规则</el-button>
        </el-card>
      </el-col>

      <!-- 枚举选项 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><b>注册选项（部门 / 职级 / 岗位）</b></template>
          <el-form label-width="140px" size="small">
            <el-form-item label="部门"><el-input v-model="enums.departments_text" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="职级"><el-input v-model="enums.job_levels_text" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="岗位"><el-input v-model="enums.positions_text" placeholder="逗号分隔" /></el-form-item>
          </el-form>
          <el-button type="primary" :loading="saving" @click="save('enums')">保存选项</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const saving = ref(false)
const vision = reactive({ device: 'gpu:0', conf_threshold: 0.75, agg_weights_text: '0.8,0.2', max_side: 1600 })
const llm = reactive({ model: '', base_url: '', temperature: 0.1, timeout_seconds: 120, system_prompt: '' })
const rules = reactive({ company_name: '', company_tax_id: '', max_age_days: 365, per_claim_limit: 5000, per_month_limit: 20000, sensitive_text: '', tax_rates_text: '', deduplicate_no: true, check_arithmetic: true, require_buyer_match: true, hard_fail_skips_llm: true })
const enums = reactive({ departments_text: '', job_levels_text: '', positions_text: '' })

function split(text) { return String(text || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean) }

function parseV(v) {
  vision.device = v.device || 'gpu:0'
  vision.conf_threshold = v.conf_threshold ?? 0.75
  vision.agg_weights_text = (v.agg_weights || [0.8, 0.2]).join(',')
  vision.max_side = v.max_side || 1600
}
function parseL(l) {
  Object.assign(llm, { model: l.model || '', base_url: l.base_url || '', temperature: l.temperature ?? 0.1, timeout_seconds: l.timeout_seconds || 120, system_prompt: l.system_prompt || '' })
}
function parseR(r) {
  rules.company_name = r.company_name || ''
  rules.company_tax_id = r.company_tax_id || ''
  rules.max_age_days = r.max_age_days ?? 365
  rules.per_claim_limit = r.per_claim_limit ?? 5000
  rules.per_month_limit = r.per_month_limit ?? 20000
  rules.sensitive_text = (r.sensitive_categories || []).join(',')
  rules.tax_rates_text = (r.allow_tax_rates || []).join(',')
  rules.deduplicate_no = r.deduplicate_no !== false
  rules.check_arithmetic = r.check_arithmetic !== false
  rules.require_buyer_match = r.require_buyer_match !== false
  rules.hard_fail_skips_llm = r.hard_fail_skips_llm !== false
}
function parseE(e) {
  enums.departments_text = (e.departments || []).join(',')
  enums.job_levels_text = (e.job_levels || []).join(',')
  enums.positions_text = (e.positions || []).join(',')
}

onMounted(async () => {
  try {
    const all = await api.get('/config')
    parseV(all.vision || {})
    parseL(all.llm || {})
    parseR(all.rules || {})
    parseE(all.enums || {})
  } catch (e) {}
})

async function save(section) {
  saving.value = true
  try {
    let value
    if (section === 'vision') value = { device: vision.device, conf_threshold: vision.conf_threshold, agg_weights: split(vision.agg_weights_text).map(Number).filter((n) => !isNaN(n)), max_side: vision.max_side }
    if (section === 'llm') value = { model: llm.model, base_url: llm.base_url, temperature: llm.temperature, timeout_seconds: llm.timeout_seconds, system_prompt: llm.system_prompt }
    if (section === 'rules') value = { company_name: rules.company_name, company_tax_id: rules.company_tax_id, max_age_days: rules.max_age_days, per_claim_limit: rules.per_claim_limit, per_month_limit: rules.per_month_limit, sensitive_categories: split(rules.sensitive_text), allow_tax_rates: split(rules.tax_rates_text), deduplicate_no: rules.deduplicate_no, check_arithmetic: rules.check_arithmetic, require_buyer_match: rules.require_buyer_match, hard_fail_skips_llm: rules.hard_fail_skips_llm, sensitive_requires_note: true }
    if (section === 'enums') value = { departments: split(enums.departments_text), job_levels: split(enums.job_levels_text), positions: split(enums.positions_text) }
    await api.put('/config', { section, value })
    ElMessage.success('已保存并即时生效')
  } catch (e) {} finally { saving.value = false }
}
</script>

<style scoped>
.page { padding: 16px; background: #f0f2f5; height: 100%; overflow-y: auto; box-sizing: border-box; }
.page h3 { margin: 0 0 14px; }
.tip { color: #909399; font-size: 12px; margin-left: 10px; font-weight: normal; }
.tip2 { color: #909399; font-size: 12px; margin-left: 8px; }
</style>

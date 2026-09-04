<template>
  <div class="model-config-page">
    <FaAiPageHeader title="模型配置" />

    <ElCard shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <span>对话模型</span>
            <ElTag effect="plain" type="info">{{ protocolLabel }}</ElTag>
          </div>
          <div class="header-actions">
            <ElButton :icon="Refresh" :loading="loading" @click="loadConfig">刷新</ElButton>
            <ElButton v-auth="'module_ai:model_config:update'" type="primary" :icon="Check" :loading="saving" @click="saveConfig">
              保存
            </ElButton>
          </div>
        </div>
      </template>

      <ElForm ref="formRef" v-loading="loading" :model="form" :rules="rules" class="model-form" label-width="104px">
        <ElFormItem label="接口协议" prop="chat_protocol">
          <ElSelect v-model="form.chat_protocol" :disabled="!canEdit" class="form-control">
            <ElOption label="OpenAI-compatible" value="openai" />
            <ElOption label="Anthropic Claude" value="anthropic" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="API 地址" prop="openai_base_url">
          <ElInput v-model="form.openai_base_url" :disabled="!canEdit" autocomplete="url" />
        </ElFormItem>
        <ElFormItem label="模型名称" prop="openai_model">
          <ElInput v-model="form.openai_model" :disabled="!canEdit" autocomplete="off" />
        </ElFormItem>
        <ElFormItem label="API Key" prop="openai_api_key">
          <ElInput v-model="form.openai_api_key" :disabled="!canEdit" type="password" show-password autocomplete="new-password" />
          <ElTag class="key-status" :type="config?.openai_api_key_configured ? 'success' : 'danger'" effect="plain">
            {{ config?.openai_api_key_configured ? "已配置" : "未配置" }}
          </ElTag>
        </ElFormItem>
      </ElForm>

      <ElDivider content-position="left">向量运行状态</ElDivider>
      <div class="vector-toolbar">
        <span class="field-hint">向量模型由云面板统一配置；同步不会传递 Provider Key。</span>
        <ElButton
          v-if="canEdit"
          v-auth="'module_ai:model_config:update'"
          type="primary"
          plain
          :icon="Refresh"
          :loading="syncingEmbedding"
          @click="syncEmbeddingModel"
        >
          从云面板同步向量模型
        </ElButton>
      </div>
      <ElAlert
        v-if="requiresReindex"
        class="reindex-alert"
        title="向量模型已变化，请重新索引或清理旧集合后再检索。"
        type="warning"
        :closable="false"
        show-icon
      />
      <ElDescriptions :column="2" border>
        <ElDescriptionsItem label="向量来源">
          <ElTag :type="config?.embedding_provider === 'local' ? 'success' : 'warning'">
            {{ config?.embedding_provider || "-" }}
          </ElTag>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="向量模型">{{ embeddingModelLabel }}</ElDescriptionsItem>
        <ElDescriptionsItem label="Chroma 持久化目录">{{ config?.chroma_persist_dir || "-" }}</ElDescriptionsItem>
        <ElDescriptionsItem label="Chroma 集合">{{ config?.chroma_collection_name || "-" }}</ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import FaAiPageHeader from "@/views/module_ai/components/FaAiPageHeader.vue";
import { Check, Refresh } from "@element-plus/icons-vue";
import { useAuth } from "@/hooks/core/useAuth";
import AiChatAPI, { type AiModelConfig, type AiModelConfigUpdate } from "@/api/module_ai/chat";

defineOptions({ name: "AiModelConfig" });

const loading = ref(false);
const saving = ref(false);
const syncingEmbedding = ref(false);
const requiresReindex = ref(false);
const config = ref<AiModelConfig>();
const formRef = ref<FormInstance>();
const { hasAuth } = useAuth();
const canEdit = computed(() => hasAuth("module_ai:model_config:update"));
const form = reactive<AiModelConfigUpdate>({
  chat_protocol: "openai",
  openai_base_url: "",
  openai_model: "",
  openai_api_key: "",
});
const rules: FormRules<AiModelConfigUpdate> = {
  openai_base_url: [{ required: true, message: "请输入 API 地址", trigger: "blur" }],
  openai_model: [{ required: true, message: "请输入模型名称", trigger: "blur" }],
};

const embeddingModelLabel = computed(() => {
  if (!config.value) return "-";
  return config.value.embedding_model || (
    config.value.embedding_provider === "local"
      ? config.value.local_embedding_model
      : config.value.openai_embedding_model
  ) || "-";
});

const protocolLabel = computed(() => (form.chat_protocol === "anthropic" ? "Anthropic Claude" : "OpenAI-compatible"));

const applyConfig = (value?: AiModelConfig) => {
  config.value = value;
  if (!value) return;
  form.chat_protocol = value.chat_protocol;
  form.openai_base_url = value.openai_base_url;
  form.openai_model = value.openai_model;
  form.openai_api_key = "";
};

const syncEmbeddingModel = async () => {
  syncingEmbedding.value = true;
  try {
    const res = await AiChatAPI.syncEmbeddingModel();
    const result = res.data?.data;
    if (!result) return;
    applyConfig(result.config);
    requiresReindex.value = result.requires_reindex;
    ElMessage.success(
      result.requires_reindex ? "向量模型已同步，请重新索引" : "向量模型已同步"
    );
  } finally {
    syncingEmbedding.value = false;
  }
};

const loadConfig = async () => {
  loading.value = true;
  requiresReindex.value = false;
  try {
    const res = await AiChatAPI.getModelConfig();
    applyConfig(res.data?.data);
  } finally {
    loading.value = false;
  }
};

const saveConfig = async () => {
  await formRef.value?.validate();
  saving.value = true;
  try {
    const body: AiModelConfigUpdate = {
      chat_protocol: form.chat_protocol,
      openai_base_url: form.openai_base_url,
      openai_model: form.openai_model,
    };
    if (form.openai_api_key?.trim()) body.openai_api_key = form.openai_api_key.trim();
    const res = await AiChatAPI.updateModelConfig(body);
    applyConfig(res.data?.data);
    ElMessage.success("模型配置已保存");
  } finally {
    saving.value = false;
  }
};

onMounted(loadConfig);
</script>

<style scoped>
.model-config-page {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-title,
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-form {
  max-width: 760px;
}

.form-control {
  width: 100%;
}

.key-status {
  margin-top: 8px;
}

.vector-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.reindex-alert {
  margin-bottom: 12px;
}

@media (max-width: 640px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .vector-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

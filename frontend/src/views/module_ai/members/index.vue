<template>
  <div class="members-page">
    <FaAiPageHeader
      title="员工与知识库权限"
      description="员工账号和产品权限由云面板维护，本页只配置客户知识库的访问范围。"
    >
      <template #actions>
        <ElButton :icon="Refresh" :loading="loading" @click="loadData">刷新</ElButton>
        <ElButton
          v-auth="'module_ai:member:create'"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          添加员工
        </ElButton>
      </template>
    </FaAiPageHeader>

    <ElCard shadow="never">
      <FaAsyncState
        v-if="loading || loadError"
        :state="loading ? 'loading' : 'error'"
        :title="loadError ? '员工目录加载失败' : undefined"
        :description="loadError ? '请检查客户知识库到云面板的服务连接后重试。' : undefined"
      >
        <template #action>
          <ElButton :icon="Refresh" @click="loadData">重试</ElButton>
        </template>
      </FaAsyncState>

      <FaAsyncState
        v-else-if="rows.length === 0"
        state="empty"
        title="暂无员工"
        description="添加员工后，再为员工配置可访问的知识库。"
      >
        <template #action>
          <ElButton v-auth="'module_ai:member:create'" type="primary" :icon="Plus" @click="openCreate">
            添加员工
          </ElButton>
        </template>
      </FaAsyncState>

      <ElTable v-else :data="rows" row-key="user_id" border>
        <ElTableColumn prop="username" label="账号" min-width="150" show-overflow-tooltip />
        <ElTableColumn prop="name" label="姓名" min-width="120" show-overflow-tooltip />
        <ElTableColumn prop="email" label="邮箱" min-width="190" show-overflow-tooltip />
        <ElTableColumn label="账号状态" width="100">
          <template #default="{ row }">
            <ElTag :type="row.status === 0 ? 'success' : 'info'">
              {{ row.status === 0 ? "启用" : "停用" }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="知识库权限" min-width="220">
          <template #default="{ row }">
            <template v-if="row.knowledge_enabled">
              <ElTag v-if="row.knowledge_base_ids.length === 0" type="warning" effect="plain">
                未授权
              </ElTag>
              <span v-else class="base-summary">{{ baseSummary(row.knowledge_base_ids) }}</span>
            </template>
            <ElTag v-else type="info" effect="plain">云端权限已关闭</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-auth="'module_ai:access:update'"
              link
              type="primary"
              :icon="Key"
              @click="openAccess(row)"
            >
              配置知识库
            </ElButton>
            <ElButton
              v-auth="'module_ai:member:update'"
              link
              type="primary"
              :icon="EditPen"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElCard>

    <ElDialog v-model="memberDialogVisible" :title="editingUserId ? '编辑员工' : '添加员工'" width="560px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px">
        <ElFormItem label="员工账号" prop="username">
          <ElInput v-model="form.username" :disabled="editingUserId !== null" autocomplete="username" />
        </ElFormItem>
        <ElFormItem v-if="!editingUserId" label="初始密码" prop="password">
          <ElInput v-model="form.password" type="password" show-password autocomplete="new-password" />
        </ElFormItem>
        <ElFormItem label="姓名" prop="name">
          <ElInput v-model="form.name" maxlength="32" />
        </ElFormItem>
        <ElFormItem label="邮箱" prop="email">
          <ElInput v-model="form.email" type="email" autocomplete="email" />
        </ElFormItem>
        <ElFormItem label="账号状态">
          <ElSwitch v-model="form.status" :active-value="0" :inactive-value="1" active-text="启用" inactive-text="停用" />
        </ElFormItem>
        <ElFormItem v-if="editingUserId === null" label="产品权限">
          <div class="capability-list">
            <ElCheckbox v-model="form.desktop_enabled">桌面端</ElCheckbox>
            <ElCheckbox v-model="form.knowledge_enabled">知识库</ElCheckbox>
            <ElCheckbox v-model="form.model_enabled">模型服务</ElCheckbox>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="memberDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="submitMember">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="accessDialogVisible" title="配置知识库权限" width="520px">
      <ElAlert
        v-if="accessMember && !accessMember.knowledge_enabled"
        title="云端知识库权限已关闭"
        description="当前员工即使配置了本地 ACL，也不会获得知识库访问权限。"
        type="warning"
        :closable="false"
        show-icon
        class="access-alert"
      />
      <ElForm label-width="100px">
        <ElFormItem label="员工账号">
          <span>{{ accessMember?.username || "-" }}</span>
        </ElFormItem>
        <ElFormItem label="可访问知识库">
          <ElSelect
            v-model="selectedKnowledgeBaseIds"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            class="base-select"
            placeholder="请选择知识库"
          >
            <ElOption v-for="item in bases" :key="item.id" :label="item.name" :value="item.id || 0" />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="accessDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="accessSaving" @click="submitAccess">保存权限</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { EditPen, Key, Plus, Refresh } from "@element-plus/icons-vue";
import KnowledgeAPI, {
  type KbMember,
  type KbMemberCreateForm,
  type KbMemberUpdateForm,
  type KnowledgeBase,
} from "@/api/module_ai/knowledge";
import FaAiPageHeader from "@/views/module_ai/components/FaAiPageHeader.vue";
import FaAsyncState from "@/components/feedback/fa-async-state/index.vue";

defineOptions({ name: "AiKnowledgeMembers" });

const loading = ref(false);
const loadError = ref(false);
const saving = ref(false);
const accessSaving = ref(false);
const rows = ref<KbMember[]>([]);
const bases = ref<KnowledgeBase[]>([]);
const memberDialogVisible = ref(false);
const accessDialogVisible = ref(false);
const editingUserId = ref<number | null>(null);
const accessMember = ref<KbMember>();
const selectedKnowledgeBaseIds = ref<number[]>([]);
const formRef = ref<FormInstance>();

const form = reactive<KbMemberCreateForm>({
  username: "",
  password: "",
  name: "",
  email: "",
  status: 0,
  desktop_enabled: true,
  knowledge_enabled: true,
  model_enabled: true,
});

const rules: FormRules<KbMemberCreateForm> = {
  username: [{ required: true, message: "请输入员工账号", trigger: "blur" }],
  password: [{ required: true, min: 6, message: "初始密码至少 6 位", trigger: "blur" }],
  name: [{ required: true, message: "请输入员工姓名", trigger: "blur" }],
  email: [{ type: "email", message: "请输入有效邮箱", trigger: "blur" }],
};

const baseNameMap = computed(() => new Map(bases.value.map((item) => [item.id, item.name])));

const baseSummary = (ids: number[]) => {
  const names = ids.map((id) => baseNameMap.value.get(id) || `知识库 ${id}`);
  return names.length > 3 ? `${names.slice(0, 3).join("、")} 等 ${names.length} 个` : names.join("、");
};

const loadData = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    const [membersResponse, basesResponse] = await Promise.all([
      KnowledgeAPI.listMembers(),
      KnowledgeAPI.optionselect(),
    ]);
    rows.value = membersResponse.data?.data || [];
    bases.value = (basesResponse.data?.data || []).filter((item) => item.id != null);
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const resetForm = () => {
  Object.assign(form, {
    username: "",
    password: "",
    name: "",
    email: "",
    status: 0,
    desktop_enabled: true,
    knowledge_enabled: true,
    model_enabled: true,
  });
};

const openCreate = () => {
  editingUserId.value = null;
  resetForm();
  memberDialogVisible.value = true;
};

const openEdit = (member: KbMember) => {
  editingUserId.value = member.user_id;
  Object.assign(form, {
    username: member.username,
    password: "",
    name: member.name,
    email: member.email || "",
    status: member.status,
    desktop_enabled: true,
    knowledge_enabled: member.knowledge_enabled,
    model_enabled: true,
  });
  memberDialogVisible.value = true;
};

const submitMember = async () => {
  await formRef.value?.validate();
  saving.value = true;
  try {
    if (editingUserId.value === null) {
      await KnowledgeAPI.createMember({
        ...form,
        email: form.email || undefined,
      });
      ElMessage.success("员工已创建");
    } else {
      const update: KbMemberUpdateForm = {
        name: form.name,
        email: form.email || undefined,
        status: form.status,
      };
      await KnowledgeAPI.updateMember(editingUserId.value, update);
      ElMessage.success("员工信息已更新");
    }
    memberDialogVisible.value = false;
    await loadData();
  } catch {
    ElMessage.error("保存员工失败，请重试");
  } finally {
    saving.value = false;
  }
};

const openAccess = async (member: KbMember) => {
  accessMember.value = member;
  selectedKnowledgeBaseIds.value = [...member.knowledge_base_ids];
  accessDialogVisible.value = true;
  try {
    const response = await KnowledgeAPI.getMemberAccess(member.user_id);
    selectedKnowledgeBaseIds.value = response.data?.data?.knowledge_base_ids || [];
  } catch {
    ElMessage.error("读取知识库权限失败，请重试");
  }
};

const submitAccess = async () => {
  if (!accessMember.value) return;
  accessSaving.value = true;
  try {
    await KnowledgeAPI.setMemberAccess(accessMember.value.user_id, {
      knowledge_base_ids: selectedKnowledgeBaseIds.value,
    });
    ElMessage.success("知识库权限已保存");
    accessDialogVisible.value = false;
    await loadData();
  } catch {
    ElMessage.error("保存知识库权限失败，请重试");
  } finally {
    accessSaving.value = false;
  }
};

onMounted(loadData);
</script>

<style scoped>
.members-page {
  min-width: 0;
}

.base-summary {
  line-height: 1.5;
  color: var(--el-text-color-regular);
}

.capability-list {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
}

.base-select {
  width: min(100%, 360px);
}

.access-alert {
  margin-bottom: 18px;
}

@media (width <= 720px) {
  .base-select {
    width: 100%;
  }
}
</style>

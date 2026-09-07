<template>
  <div class="home-workspace">
    <FaPageHeader
      title="知识库工作台"
      description="管理知识资产、验证检索质量并控制员工访问范围。"
    >
      <template #status>
        <ElTag type="info" effect="plain">客户知识库</ElTag>
      </template>
    </FaPageHeader>

    <Banner class="home-hero" />

    <section class="workspace-section home-surface" aria-labelledby="workspace-entry-title">
      <div class="section-heading section-heading--workspace">
        <div>
          <span class="section-eyebrow">KNOWLEDGE ROUTES</span>
          <h2 id="workspace-entry-title">从这里开始</h2>
          <p>把日常维护拆成清晰的工作入口，当前账号没有权限的功能不会出现在这里。</p>
        </div>
        <div class="section-meta" aria-label="可用知识库入口数量">
          <strong>{{ knowledgeMenus.length }}</strong>
          <span>个入口</span>
        </div>
      </div>

      <div v-if="knowledgeMenus.length" class="workspace-action-grid">
        <button
          v-for="menu in knowledgeMenus"
          :key="menu.id ?? menu.route_name ?? menu.name"
          class="workspace-action"
          type="button"
          @click="navigateToMenu(menu, knowledgeRootPath)"
        >
          <span class="workspace-action__index" aria-hidden="true"></span>
          <span class="workspace-action__icon">
            <FaSvgIcon :icon="menu.icon || 'ri:arrow-right-up-line'" />
          </span>
          <span class="workspace-action__content">
            <strong>{{ menu.title || menu.name || "未命名入口" }}</strong>
            <span>{{ getWorkspaceDescription(menu) }}</span>
          </span>
          <span class="workspace-action__arrow" aria-hidden="true">
            <FaSvgIcon icon="ri:arrow-right-line" />
          </span>
        </button>
      </div>
      <ElEmpty v-else description="当前账号暂无可用的知识库入口" :image-size="64" />
    </section>

    <section class="overview-section" aria-labelledby="overview-title">
      <div class="overview-intro">
        <span class="section-eyebrow">CONTROL ROOM</span>
        <h2 id="overview-title">权限与运行概览</h2>
        <p>以下状态来自当前会话、动态菜单和后端健康探针。</p>
      </div>

      <div class="metrics-grid" aria-label="当前系统状态">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card home-surface">
          <div class="metric-card__head">
            <div>
              <span class="metric-card__label">{{ metric.label }}</span>
              <div class="metric-card__value">
                {{ metric.value }}<small>{{ metric.unit }}</small>
              </div>
            </div>
            <span class="metric-card__icon" :class="`metric-card__icon--${metric.tone}`">
              <FaSvgIcon :icon="metric.icon" />
            </span>
          </div>
          <p>{{ metric.description }}</p>
        </article>
      </div>
    </section>

    <section v-if="canViewModelUsage" class="usage-section home-surface" aria-labelledby="model-usage-title">
      <div class="section-heading">
        <div>
          <span class="section-eyebrow">USAGE / LAST 7 DAYS</span>
          <h2 id="model-usage-title">模型使用记录</h2>
          <p>
            数据来自云面板已接收的模型日志，展示近 7 日总量和按用户统计，不包含提示词或响应内容。
          </p>
        </div>
        <ElTag
          :type="usageState === 'ready' ? 'success' : usageState === 'loading' ? 'info' : 'warning'"
          effect="light"
        >
          {{ usageState === "ready" ? "已同步" : usageState === "loading" ? "加载中" : "暂不可用" }}
        </ElTag>
      </div>

      <div
        v-if="billingState === 'ready' && billingSummary"
        class="billing-summary"
        aria-label="企业额度"
      >
        <div class="billing-summary__item billing-summary__item--primary">
          <span>企业可用额度</span>
          <strong>{{ formatCny(billingSummary.totalAvailableCny) }}</strong>
        </div>
        <div class="billing-summary__item">
          <span>免费额度剩余</span>
          <strong>{{ formatCny(billingSummary.freeRemainingCny) }}</strong>
        </div>
        <div class="billing-summary__item">
          <span>付费余额</span>
          <strong>{{ formatCny(billingSummary.paidBalanceCny) }}</strong>
        </div>
        <div class="billing-summary__item">
          <span>企业员工</span>
          <strong>{{ formatTokenCount(billingSummary.memberCount) }} 人</strong>
        </div>
      </div>
      <div v-else-if="billingState === 'unavailable'" class="billing-hint">
        <FaSvgIcon icon="ri:information-line" />
        <span>{{ billingError || "暂时无法读取云端额度，Token 用量仍可查看。" }}</span>
      </div>

      <div v-if="usageState === 'loading'" class="usage-empty" aria-live="polite">
        <ElSkeleton :rows="2" animated />
      </div>
      <div v-else-if="usageState === 'unavailable'" class="usage-empty">
        <FaSvgIcon icon="ri:error-warning-line" />
        <span>{{ usageError || "暂时无法读取云面板用量" }}</span>
      </div>
      <template v-else-if="usageSummary">
        <div class="usage-metrics">
          <div class="usage-metric">
            <span>总 Token</span>
            <strong>{{ formatTokenCount(usageSummary.total_tokens) }}</strong>
          </div>
          <div class="usage-metric">
            <span>输入 Token</span>
            <strong>{{ formatTokenCount(usageSummary.prompt_tokens) }}</strong>
          </div>
          <div class="usage-metric">
            <span>输出 Token</span>
            <strong>{{ formatTokenCount(usageSummary.completion_tokens) }}</strong>
          </div>
          <div class="usage-metric">
            <span>模型请求</span>
            <strong>{{ formatTokenCount(usageSummary.request_count) }}<small>次</small></strong>
          </div>
          <div class="usage-metric">
            <span>费用</span>
            <strong>{{ formatCny(usageSummary.total_cost_cny) }}</strong>
          </div>
        </div>

        <div v-if="usageSummary.request_count" class="usage-days" aria-label="每日 Token 消耗">
          <div v-for="item in usageSummary.items" :key="item.day" class="usage-day">
            <span>{{ formatUsageDay(item.day) }}</span>
            <strong>{{ formatTokenCount(item.total_tokens) }} Token</strong>
            <span
              >{{ formatTokenCount(item.request_count) }} 次请求 ·
              {{ formatCny(item.total_cost_cny) }}</span
            >
          </div>
        </div>
        <div
          v-if="usageSummary.users?.length"
          class="usage-users"
          aria-labelledby="model-usage-users-title"
        >
          <h3 id="model-usage-users-title" class="usage-users__title">按用户统计</h3>
          <ElTable :data="usageSummary.users || []" size="small" max-height="360">
            <ElTableColumn prop="username" label="用户" min-width="150" show-overflow-tooltip />
            <ElTableColumn label="总 Token" min-width="120" align="right">
              <template #default="{ row }">{{ formatTokenCount(row.total_tokens) }}</template>
            </ElTableColumn>
            <ElTableColumn label="费用" min-width="110" align="right">
              <template #default="{ row }">{{ formatCny(row.total_cost_cny) }}</template>
            </ElTableColumn>
            <ElTableColumn label="输入 Token" min-width="120" align="right">
              <template #default="{ row }">{{ formatTokenCount(row.prompt_tokens) }}</template>
            </ElTableColumn>
            <ElTableColumn label="输出 Token" min-width="120" align="right">
              <template #default="{ row }">{{ formatTokenCount(row.completion_tokens) }}</template>
            </ElTableColumn>
            <ElTableColumn label="请求次数" min-width="100" align="right">
              <template #default="{ row }">{{ formatTokenCount(row.request_count) }}</template>
            </ElTableColumn>
          </ElTable>
        </div>
        <ElEmpty
          v-if="!usageSummary.request_count"
          description="近 7 日暂无模型用量"
          :image-size="72"
        />
      </template>
    </section>

    <section class="dashboard-grid" :class="{ 'dashboard-grid--solo': !canViewLoginTrend }">
      <LoginTrend v-if="canViewLoginTrend" class="home-login-trend" />

      <ElCard shadow="never" class="home-card account-card">
        <template #header>
          <div class="section-heading">
            <div>
              <span class="section-eyebrow">SESSION PROFILE</span>
              <h2>当前账号</h2>
              <p>登录态和授权信息来自当前会话。</p>
            </div>
            <ElTag :type="currentUser.status === 1 ? 'danger' : 'success'" effect="light">
              {{ currentUser.status === 1 ? "已停用" : "正常" }}
            </ElTag>
          </div>
        </template>

        <dl class="account-list">
          <div>
            <dt>账号</dt>
            <dd>{{ currentUser.username || "未加载" }}</dd>
          </div>
          <div>
            <dt>显示名称</dt>
            <dd>{{ currentUser.name || "未加载" }}</dd>
          </div>
          <div>
            <dt>授权角色</dt>
            <dd>{{ roleLabel }}</dd>
          </div>
          <div>
            <dt>最近登录</dt>
            <dd>{{ currentUser.last_login || "暂无记录" }}</dd>
          </div>
        </dl>
      </ElCard>
    </section>

    <section class="checklist-section home-surface" aria-labelledby="session-check-title">
      <div class="section-heading">
        <div>
          <span class="section-eyebrow">READINESS CHECK</span>
          <h2 id="session-check-title">会话检查</h2>
          <p>快速确认当前后台是否完成认证、菜单、权限和基础依赖检查。</p>
        </div>
        <div class="section-actions">
          <span
            class="check-summary"
            :class="allChecksPassed ? 'check-summary--success' : 'check-summary--warning'"
          >
            {{ allChecksPassed ? "状态正常" : "需要检查" }}
          </span>
          <ElTooltip v-if="canViewHealth" content="重新检查系统健康" placement="top">
            <ElButton
              class="health-refresh-button"
              size="small"
              plain
              circle
              :loading="healthLoading"
              aria-label="重新检查系统健康"
              @click="loadHealthStatus"
            >
              <FaSvgIcon icon="ri:refresh-line" />
            </ElButton>
          </ElTooltip>
        </div>
      </div>

      <ul class="check-list">
        <li v-for="item in checks" :key="item.label" class="check-item">
          <span
            class="check-item__icon"
            :class="item.passed ? 'check-item__icon--success' : 'check-item__icon--warning'"
          >
            <FaSvgIcon :icon="item.passed ? 'ri:check-line' : 'ri:error-warning-line'" />
          </span>
          <span class="check-item__content">
            <strong>{{ item.label }}</strong>
            <span>{{ item.detail }}</span>
          </span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import KnowledgeAPI, {
  type ModelBillingSummary,
  type ModelUsageSummary,
} from "@/api/module_ai/knowledge";
import HealthAPI, { type HealthReadiness } from "@/api/module_common/health";
import type { MenuTable } from "@/api/module_platform/menu";
import { MenuTypeEnum } from "@/enums/system/menu.enum";
import { useUserStore } from "@stores";
import { HttpError } from "@utils";
import FaPageHeader from "@/components/layouts/fa-page-header/index.vue";
import Banner from "./modules/banner.vue";
import LoginTrend from "./modules/login-trend.vue";

defineOptions({ name: "Home", inheritAttrs: false });

type DashboardMetric = {
  label: string;
  value: number | string;
  unit: string;
  description: string;
  icon: string;
  tone: "primary" | "success" | "warning" | "info";
};

type CheckItem = {
  label: string;
  detail: string;
  passed: boolean;
};

type HealthState = "loading" | "healthy" | "degraded" | "unavailable";
type UsageState = "loading" | "ready" | "unavailable";
type BillingState = "loading" | "ready" | "unavailable";

type HealthPresentation = Pick<DashboardMetric, "value" | "icon" | "tone">;

const HEALTH_REFRESH_INTERVAL = 30_000;
const dependencyLabels: Record<keyof HealthReadiness["dependencies"], string> = {
  database: "数据库",
  redis: "Redis",
};
const healthPresentations: Record<HealthState, HealthPresentation> = {
  loading: { value: "检查中", icon: "ri:heart-pulse-line", tone: "info" },
  healthy: { value: "正常", icon: "ri:heart-pulse-line", tone: "success" },
  degraded: { value: "需处理", icon: "ri:error-warning-line", tone: "warning" },
  unavailable: { value: "不可用", icon: "ri:error-warning-line", tone: "warning" },
};

const userStore = useUserStore();
const healthState = ref<HealthState>("loading");
const healthData = ref<HealthReadiness | null>(null);
const healthError = ref("");
const healthLoading = ref(false);
const usageState = ref<UsageState>("loading");
const usageSummary = ref<ModelUsageSummary | null>(null);
const usageError = ref("");
const billingState = ref<BillingState>("loading");
const billingSummary = ref<ModelBillingSummary | null>(null);
const billingError = ref("");
const router = useRouter();
const currentUser = computed(() => userStore.basicInfo);
const canViewHealth = computed(() => Boolean(currentUser.value.is_superuser));
const canViewLoginTrend = computed(
  () => canViewHealth.value || userStore.getPerms.includes("module_system:login_log:query")
);
const canViewModelUsage = computed(
  () => canViewHealth.value || userStore.getPerms.includes("module_ai:member:query")
);
const rootMenus = computed(() =>
  userStore.getRouteList.filter((menu) => menu.type !== MenuTypeEnum.BUTTON)
);
const knowledgeRoot = computed(() =>
  rootMenus.value.find((menu) => menu.route_name === "AI" || menu.route_path === "/ai")
);
const knowledgeRootPath = computed(() =>
  normalizeMenuPath(knowledgeRoot.value?.route_path || knowledgeRoot.value?.redirect || "")
);
const knowledgeMenus = computed(
  () => knowledgeRoot.value?.children?.filter((menu) => menu.type !== MenuTypeEnum.BUTTON && !menu.hidden) ?? []
);
const permissionCount = computed(() => userStore.getPerms.length);
const roleCount = computed(() => currentUser.value.roles?.length ?? 0);
const menuCount = computed(() => countMenuEntries(userStore.getRouteList));
const roleLabel = computed(() => {
  if (currentUser.value.is_superuser) return "超级管理员";
  return currentUser.value.role_names?.filter(Boolean).join("、") || `${roleCount.value} 个角色`;
});
const healthDescription = computed(() => {
  if (healthState.value === "loading") return "正在检查数据库、Redis 和磁盘使用率";
  if (!healthData.value) return healthError.value || "系统健康检查暂不可用";

  const dependencySummary = Object.entries(healthData.value.dependencies)
    .map(([name, dependency]) => {
      const label = dependencyLabels[name as keyof HealthReadiness["dependencies"]] || name;
      if (!dependency.enabled) return `${label} 未启用`;
      if (dependency.status !== 1) return `${label} 异常`;
      return `${label} ${dependency.latency_ms === null ? "正常" : `${dependency.latency_ms}ms`}`;
    })
    .join(" · ");
  const diskSummary =
    healthData.value.disk_usage >= 0 ? `磁盘 ${healthData.value.disk_usage}%` : "磁盘数据不可用";
  return `${dependencySummary} · ${diskSummary}`;
});
const healthMetric = computed<DashboardMetric>(() => {
  return {
    label: "系统健康",
    unit: "",
    description: healthDescription.value,
    ...healthPresentations[healthState.value],
  };
});

const metrics = computed<DashboardMetric[]>(() => [
  {
    label: "可见菜单",
    value: menuCount.value,
    unit: "项",
    description: "当前账号可访问的页面入口",
    icon: "ri:layout-grid-line",
    tone: "primary",
  },
  {
    label: "权限点",
    value: permissionCount.value,
    unit: "项",
    description: "后端下发并用于 RBAC 校验",
    icon: "ri:shield-check-line",
    tone: "success",
  },
  {
    label: "授权角色",
    value: currentUser.value.is_superuser ? "超管" : roleCount.value,
    unit: currentUser.value.is_superuser ? "" : "个",
    description: "当前账号的角色授权状态",
    icon: "ri:user-settings-line",
    tone: "warning",
  },
  ...(canViewHealth.value ? [healthMetric.value] : []),
]);

const checks = computed<CheckItem[]>(() => [
  {
    label: "认证会话",
    detail: userStore.isLogin ? "访问令牌有效，当前用户已登录" : "当前没有可用的登录会话",
    passed: userStore.isLogin,
  },
  {
    label: "用户资料",
    detail: currentUser.value.username ? "用户资料已从后端加载" : "用户资料尚未加载",
    passed: Boolean(currentUser.value.username),
  },
  {
    label: "动态菜单",
    detail: userStore.getHasGetRoute
      ? `${rootMenus.value.length} 个一级模块已注册`
      : "动态菜单尚未注册",
    passed: userStore.getHasGetRoute,
  },
  {
    label: "权限集",
    detail: currentUser.value.is_superuser
      ? "超级管理员权限已生效"
      : `${permissionCount.value} 个权限点已加载`,
    passed: Boolean(currentUser.value.is_superuser || permissionCount.value),
  },
  ...(canViewHealth.value
    ? [
        {
          label: "基础依赖",
          detail: healthDescription.value,
          passed: healthState.value === "healthy",
        },
      ]
    : []),
]);

const allChecksPassed = computed(() => checks.value.every((item) => item.passed));

const workspaceDescriptions: Record<string, string> = {
  Knowledge: "创建知识库并维护资源边界",
  Document: "上传、整理并追踪索引文档",
  Retrieval: "用真实权限验证召回质量",
  KnowledgeMembers: "同步员工并配置访问权限",
};

function getWorkspaceDescription(menu: MenuTable): string {
  return (
    workspaceDescriptions[menu.route_name || ""] ||
    menu.description ||
    "打开当前账号可用的知识库功能"
  );
}

function normalizeMenuPath(path: string): string {
  const value = path.trim();
  if (!value) return "";
  return value.startsWith("/") ? value : `/${value}`;
}

function resolveMenuPath(menu: MenuTable, parentPath: string): string {
  const directPath = menu.redirect?.trim() || menu.route_path?.trim() || "";
  if (!directPath) return normalizeMenuPath(parentPath);
  if (directPath.startsWith("/")) return directPath;

  const parent = normalizeMenuPath(parentPath);
  return parent ? `${parent.replace(/\/$/, "")}/${directPath}` : `/${directPath}`;
}

function navigateToMenu(menu: MenuTable, parentPath: string): void {
  const routeName = menu.route_name?.trim();
  if (routeName) {
    void router.push({ name: routeName });
    return;
  }

  const path = resolveMenuPath(menu, parentPath);
  if (path) void router.push(path);
}

/**
 * Counts navigable menu and child entries while excluding button permissions.
 *
 * @param menus Menu tree returned by the backend.
 * @returns Number of catalog, menu, and external-link entries.
 */
function countMenuEntries(menus: MenuTable[]): number {
  return menus.reduce((total, menu) => {
    if (menu.type === MenuTypeEnum.BUTTON) return total + countMenuEntries(menu.children ?? []);
    return total + 1 + countMenuEntries(menu.children ?? []);
  }, 0);
}

/**
 * Validates a readiness payload before it is rendered on the dashboard.
 *
 * @param value Untrusted response payload from the health endpoint.
 * @returns Whether the payload has the required dependency metrics.
 */
function isHealthReadiness(value: unknown): value is HealthReadiness {
  if (!value || typeof value !== "object") return false;

  const candidate = value as Record<string, unknown>;
  if (
    (candidate.status !== 0 && candidate.status !== 1) ||
    typeof candidate.disk_usage !== "number"
  )
    return false;
  if (!candidate.dependencies || typeof candidate.dependencies !== "object") return false;

  return ["database", "redis"].every((name) => {
    const dependency = (candidate.dependencies as Record<string, unknown>)[name];
    if (!dependency || typeof dependency !== "object") return false;

    const dependencyData = dependency as Record<string, unknown>;
    if (typeof dependencyData.enabled !== "boolean") return false;
    const status = dependencyData.status;
    return status === 0 || status === 1;
  });
}

/**
 * Extracts a degraded readiness payload from a failed health probe.
 *
 * @param error Request error raised by the HTTP client.
 * @returns Readiness metrics when the server returned a structured 503 response.
 */
function extractReadinessPayload(error: unknown): HealthReadiness | null {
  if (!(error instanceof HttpError) || !error.data || typeof error.data !== "object") return null;

  const payload = (error.data as Record<string, unknown>).data;
  return isHealthReadiness(payload) ? payload : null;
}

/**
 * Refreshes dashboard health metrics without displaying global error notifications.
 *
 * @returns Promise resolved after the latest health result is recorded.
 */
async function loadHealthStatus(): Promise<void> {
  if (!canViewHealth.value || healthLoading.value) return;

  healthLoading.value = true;
  try {
    const response = await HealthAPI.getReadiness();
    const readiness = response.data.data;
    healthData.value = readiness;
    healthState.value = readiness.status === 1 ? "healthy" : "degraded";
    healthError.value = "";
  } catch (error: unknown) {
    const readiness = extractReadinessPayload(error);
    if (readiness) {
      healthData.value = readiness;
      healthState.value = "degraded";
      healthError.value = "";
      return;
    }

    healthData.value = null;
    healthState.value = "unavailable";
    healthError.value = error instanceof Error ? error.message : "健康检查请求失败";
  } finally {
    healthLoading.value = false;
  }
}

async function loadModelUsageSummary(): Promise<void> {
  if (!canViewModelUsage.value) return;

  try {
    const response = await KnowledgeAPI.getModelUsageSummary();
    usageSummary.value = response.data.data;
    usageState.value = "ready";
    usageError.value = "";
  } catch (error: unknown) {
    usageSummary.value = null;
    usageState.value = "unavailable";
    usageError.value = error instanceof Error ? error.message : "用量请求失败";
  }
}

async function loadBillingSummary(): Promise<void> {
  if (!canViewModelUsage.value) return;

  try {
    const response = await KnowledgeAPI.getBillingSummary();
    billingSummary.value = response.data.data;
    billingState.value = "ready";
    billingError.value = "";
  } catch (error: unknown) {
    billingSummary.value = null;
    billingState.value = "unavailable";
    billingError.value = error instanceof Error ? error.message : "云端额度暂不可用";
  }
}

function formatTokenCount(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(Math.max(0, value));
}

function formatCny(value: number): string {
  return `¥${Number(value || 0).toFixed(2)}`;
}

function formatUsageDay(value: string): string {
  return value.length >= 10 ? value.slice(5, 10) : value;
}

let healthRefreshTimer: number | undefined;

onMounted(() => {
  void loadModelUsageSummary();
  void loadBillingSummary();
  if (!canViewHealth.value) return;
  void loadHealthStatus();
  healthRefreshTimer = window.setInterval(() => void loadHealthStatus(), HEALTH_REFRESH_INTERVAL);
});

onUnmounted(() => {
  if (healthRefreshTimer !== undefined) window.clearInterval(healthRefreshTimer);
});
</script>

<style scoped lang="scss">
.home-workspace {
  min-width: 0;
}

.home-login-trend {
  display: block;
  margin-bottom: 20px;
}

.usage-section {
  padding: 20px;
  margin-bottom: 20px;
  background: var(--fa-color-surface, var(--el-bg-color));
  border: 1px solid var(--fa-color-border, var(--el-border-color));
  border-radius: 8px;
}

.billing-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.billing-summary__item {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
}

.billing-summary__item span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.billing-summary__item strong {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 21px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.billing-summary__item--primary strong {
  color: var(--el-color-primary);
}

.billing-hint {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.usage-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.usage-metric {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
}

.usage-metric span,
.usage-day span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.usage-metric strong {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 22px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.usage-metric small {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 500;
}

.usage-days {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.usage-users {
  margin-top: 20px;
}

.usage-users__title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.usage-day {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 38px;
  padding: 0 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.usage-day:last-child {
  border-bottom: 0;
}

.usage-day strong {
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.usage-empty {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
  min-height: 104px;
  color: var(--el-text-color-secondary);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.metric-card,
.home-card,
.checklist-section {
  background: var(--fa-color-surface, var(--el-bg-color));
  border: 1px solid var(--fa-color-border, var(--el-border-color));
  border-radius: 8px;
}

.metric-card {
  min-height: 142px;
  padding: 18px;
}

.metric-card__head,
.section-heading {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  justify-content: space-between;
}

.section-actions {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.health-refresh-button {
  flex: 0 0 auto;
}

.metric-card__label {
  display: block;
  font-size: 13px;
  font-weight: 650;
  color: var(--el-text-color-secondary);
}

.metric-card__value {
  margin-top: 12px;
  font-size: 28px;
  font-weight: 760;
  line-height: 1;
  color: var(--el-text-color-primary);
}

.metric-card__value small {
  margin-left: 5px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.metric-card p,
.section-heading p {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}

.metric-card__icon,
.module-row__icon,
.check-item__icon {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
}

.metric-card__icon {
  width: 40px;
  height: 40px;
  font-size: 20px;
}

.metric-card__icon--primary {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.metric-card__icon--success {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.metric-card__icon--warning {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.metric-card__icon--info {
  color: var(--el-color-info);
  background: var(--el-color-info-light-9);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  gap: 20px;
  margin-bottom: 20px;
}

.home-card :deep(.el-card__header) {
  padding: 18px 20px;
  border-bottom-color: var(--fa-color-border, var(--el-border-color));
}

.home-card :deep(.el-card__body) {
  padding: 20px;
}

.section-heading h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.section-heading p {
  margin-top: 5px;
}

.module-list {
  display: grid;
  gap: 8px;
}

.module-row {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 56px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
}

.module-row__icon {
  width: 34px;
  height: 34px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.module-row__content {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.module-row__content strong {
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.module-row__content span,
.module-row__count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.module-row__count {
  margin-left: auto;
  font-weight: 700;
  color: var(--el-color-primary);
}

.account-list {
  display: grid;
  gap: 0;
  margin: 0;
}

.account-list > div {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 13px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.account-list > div:last-child {
  border-bottom: 0;
}

.account-list dt {
  flex: 0 0 auto;
  color: var(--el-text-color-secondary);
}

.account-list dd {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
  color: var(--el-text-color-primary);
  text-align: right;
  white-space: nowrap;
}

.checklist-section {
  padding: 20px;
}

.check-summary {
  flex: 0 0 auto;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 700;
  border-radius: 5px;
}

.check-summary--success {
  color: var(--el-color-success-dark-2);
  background: var(--el-color-success-light-9);
}

.check-summary--warning {
  color: var(--el-color-warning-dark-2);
  background: var(--el-color-warning-light-9);
}

.check-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 0;
  margin: 18px 0 0;
  list-style: none;
}

.check-item {
  display: flex;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
}

.check-item__icon {
  width: 26px;
  height: 26px;
}

.check-item__icon--success {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.check-item__icon--warning {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.check-item__content {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.check-item__content strong {
  color: var(--el-text-color-primary);
}

.check-item__content span {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

@media (width <= 1100px) {
  .metrics-grid,
  .billing-summary,
  .usage-metrics,
  .check-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (width <= 640px) {
  .metrics-grid,
  .billing-summary,
  .usage-metrics,
  .check-list {
    grid-template-columns: 1fr;
  }

  .checklist-section,
  .usage-section,
  .home-card :deep(.el-card__body) {
    padding: 16px;
  }

  .usage-day {
    grid-template-columns: 58px minmax(0, 1fr);
  }

  .usage-day > span:last-child {
    grid-column: 2;
  }
}
</style>

<style scoped lang="scss">
/* Homepage visual system: a compact knowledge-operations desk rather than a generic admin dashboard. */
.home-workspace {
  min-width: 0;
  padding-bottom: 24px;
}

.home-surface,
.home-card,
.checklist-section {
  background: var(--fa-color-surface);
  border: 1px solid var(--fa-color-border);
  border-radius: var(--fa-radius-panel);
}

.workspace-section {
  padding: 24px;
  margin-bottom: 20px;
}

.section-heading {
  gap: 20px;
}

.section-heading h2,
.overview-intro h2 {
  margin: 4px 0 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--fa-color-text);
}

.section-heading p,
.overview-intro p {
  margin-top: 7px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--fa-color-text-muted);
}

.section-eyebrow {
  display: block;
  font-family: var(--fa-font-mono, ui-monospace, monospace);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--fa-color-accent);
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.section-heading--workspace {
  align-items: flex-end;
}

.section-meta {
  display: inline-flex;
  flex: 0 0 auto;
  gap: 6px;
  align-items: baseline;
  padding: 7px 10px;
  color: var(--fa-color-text-muted);
  background: color-mix(in srgb, var(--theme-color) 7%, var(--fa-color-surface));
  border: 1px solid color-mix(in srgb, var(--theme-color) 18%, var(--fa-color-border));
  border-radius: var(--fa-radius-control);
}

.section-meta strong {
  font-size: 20px;
  font-variant-numeric: tabular-nums;
  color: var(--fa-color-accent);
}

.section-meta span {
  font-size: 12px;
}

.workspace-action-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding-top: 20px;
  counter-reset: workspace-action;
}

.workspace-action {
  position: relative;
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
  min-height: 104px;
  padding: 14px;
  font: inherit;
  text-align: left;
  cursor: pointer;
  counter-increment: workspace-action;
  background: var(--fa-color-surface-raised);
  border: 1px solid var(--fa-color-border);
  border-radius: var(--fa-radius-control);
  transition:
    border-color var(--fa-motion-control) ease,
    background-color var(--fa-motion-control) ease,
    transform var(--fa-motion-control) ease;
}

.workspace-action:hover {
  background: color-mix(in srgb, var(--theme-color) 5%, var(--fa-color-surface));
  border-color: color-mix(in srgb, var(--theme-color) 34%, var(--fa-color-border));
  transform: translateY(-2px);
}

.workspace-action:focus-visible {
  outline: none;
  box-shadow: var(--fa-focus-ring);
}

.workspace-action:active {
  transform: translateY(0);
}

.workspace-action__index {
  align-self: start;
  width: 18px;
  padding-top: 2px;
  font-family: var(--fa-font-mono, ui-monospace, monospace);
  font-size: 10px;
  color: var(--fa-color-text-muted);
}

.workspace-action__index::before {
  content: counter(workspace-action, decimal-leading-zero);
}

.workspace-action__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  color: var(--fa-color-accent);
  background: color-mix(in srgb, var(--theme-color) 11%, var(--fa-color-surface));
  border-radius: 10px;
}

.workspace-action__content {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.workspace-action__content strong {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 14px;
  font-weight: 700;
  color: var(--fa-color-text);
  white-space: nowrap;
}

.workspace-action__content span {
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 12px;
  line-height: 1.45;
  color: var(--fa-color-text-muted);
  white-space: nowrap;
}

.workspace-action__arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--fa-color-text-muted);
  transition: color var(--fa-motion-control) ease, transform var(--fa-motion-control) ease;
}

.workspace-action:hover .workspace-action__arrow {
  color: var(--fa-color-accent);
  transform: translateX(3px);
}

.overview-section {
  margin-bottom: 20px;
}

.overview-intro {
  padding: 0 2px;
}

.metrics-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 0;
}

.metric-card {
  position: relative;
  min-height: 132px;
  padding: 18px;
  overflow: hidden;
  border-radius: var(--fa-radius-panel);
}

.metric-card::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  content: "";
  background: color-mix(in srgb, var(--theme-color) 38%, transparent);
  opacity: 0.7;
}

.metric-card__head {
  gap: 12px;
}

.metric-card__label {
  font-size: 12px;
  font-weight: 650;
  color: var(--fa-color-text-muted);
  letter-spacing: 0.02em;
}

.metric-card__value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  color: var(--fa-color-text);
}

.metric-card__value small {
  margin-left: 5px;
  font-size: 12px;
  font-weight: 500;
  color: var(--fa-color-text-muted);
}

.metric-card p {
  max-width: 240px;
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--fa-color-text-muted);
}

.metric-card__icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
}

.usage-section {
  padding: 24px;
  margin-bottom: 20px;
  border-radius: var(--fa-radius-panel);
}

.usage-section > .section-heading {
  align-items: flex-start;
}

.billing-summary {
  gap: 10px;
  margin-top: 20px;
}

.billing-summary__item,
.usage-metric {
  min-height: 82px;
  padding: 14px;
  background: var(--fa-color-surface-raised);
  border: 1px solid var(--fa-color-border);
  border-radius: var(--fa-radius-control);
}

.billing-summary__item span,
.usage-metric span {
  font-size: 11px;
  color: var(--fa-color-text-muted);
  letter-spacing: 0.02em;
}

.billing-summary__item strong,
.usage-metric strong {
  font-variant-numeric: tabular-nums;
  color: var(--fa-color-text);
}

.billing-summary__item strong {
  font-size: 20px;
}

.billing-summary__item--primary {
  background: color-mix(in srgb, var(--theme-color) 8%, var(--fa-color-surface));
  border-color: color-mix(in srgb, var(--theme-color) 22%, var(--fa-color-border));
}

.billing-summary__item--primary strong {
  color: var(--fa-color-accent);
}

.usage-metrics {
  gap: 10px;
  margin-top: 20px;
}

.usage-metric strong {
  font-size: 21px;
}

.usage-day {
  min-height: 42px;
  padding: 0 10px;
  border-bottom-color: var(--fa-color-border);
}

.usage-days {
  gap: 0;
  margin-top: 16px;
  border: 1px solid var(--fa-color-border);
  border-radius: var(--fa-radius-control);
}

.usage-users {
  margin-top: 22px;
}

.dashboard-grid {
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  gap: 20px;
  align-items: stretch;
  margin-bottom: 20px;
}

.dashboard-grid--solo {
  grid-template-columns: 1fr;
}

.home-login-trend {
  height: 100%;
  margin-bottom: 0;
}

.home-card {
  height: 100%;
}

.home-card :deep(.el-card__header) {
  padding: 20px 22px 16px;
  background: var(--fa-color-surface);
  border-bottom-color: var(--fa-color-border);
}

.home-card :deep(.el-card__body) {
  padding: 20px 22px;
}

.account-list > div {
  padding: 14px 0;
  border-bottom-color: var(--fa-color-border);
}

.checklist-section {
  padding: 24px;
}

.checklist-section .section-heading {
  align-items: flex-start;
}

.check-summary {
  padding: 6px 10px;
  border: 1px solid transparent;
  border-radius: 999px;
}

.check-summary--success {
  border-color: color-mix(in srgb, var(--el-color-success) 25%, var(--fa-color-border));
}

.check-summary--warning {
  border-color: color-mix(in srgb, var(--el-color-warning) 28%, var(--fa-color-border));
}

.check-list {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-top: 20px;
}

.check-item {
  min-height: 68px;
  padding: 12px;
  background: var(--fa-color-surface-raised);
  border-color: var(--fa-color-border);
  border-radius: var(--fa-radius-control);
}

@media (width <= 1100px) {
  .workspace-action-grid,
  .metrics-grid,
  .billing-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (width <= 640px) {
  .workspace-section,
  .usage-section,
  .checklist-section {
    padding: 18px;
  }

  .section-heading--workspace,
  .section-heading {
    align-items: flex-start;
  }

  .workspace-action-grid,
  .metrics-grid,
  .billing-summary {
    grid-template-columns: 1fr;
  }

  .workspace-action {
    grid-template-columns: auto auto minmax(0, 1fr) auto;
  }

  .usage-day {
    grid-template-columns: 58px minmax(0, 1fr);
  }

  .usage-day > span:last-child {
    grid-column: 2;
  }

  .section-meta {
    margin-top: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace-action,
  .workspace-action__arrow {
    transition: none;
  }
}
</style>

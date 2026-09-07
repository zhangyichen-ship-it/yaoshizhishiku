<template>
  <section class="home-command-hero" aria-label="知识库工作台概览">
    <div class="hero-grid-mark" aria-hidden="true">
      <span class="hero-grid-mark__label">KB / 01</span>
      <span class="hero-grid-mark__ring hero-grid-mark__ring--large"></span>
      <span class="hero-grid-mark__ring hero-grid-mark__ring--small"></span>
    </div>

    <div class="hero-copy">
      <div class="hero-kicker">
        <span class="hero-kicker__index">KNOWLEDGE OPERATIONS</span>
        <span class="signal-dot"></span>
        已连接
      </div>
      <h1>{{ bannerTitle }}<span class="hero-title-mark" aria-hidden="true">/</span></h1>
      <p>{{ bannerSubtitle }}</p>

      <div class="operator-card">
        <ElAvatar v-if="currentUser.avatar" :size="48" :src="currentUser.avatar" class="operator-avatar" />
        <div v-else class="operator-avatar operator-avatar--fallback">
          <ElIcon :size="24"><UserFilled /></ElIcon>
        </div>
        <div class="operator-meta">
          <strong>{{ currentUser.name }}</strong>
          <span>@{{ currentUser.username }} · {{ currentUser.description }}</span>
        </div>
        <div class="operator-login">
          <span>最近进入</span>
          <strong>{{ currentUser.last_login || "暂无记录" }}</strong>
        </div>
      </div>
    </div>

    <div class="hero-status-panel" aria-label="当前系统状态">
      <div class="status-panel-head">
        <span class="status-panel-head__title"><span class="panel-dot"></span>工作台信号</span>
        <span class="status-panel-head__code">LIVE / SESSION</span>
      </div>
      <div class="hero-status-grid">
        <article v-for="item in statusCards" :key="item.label" class="status-chip">
          <span class="status-icon" :class="`status-icon--${item.tone}`">
            <FaSvgIcon :icon="item.icon" />
          </span>
          <div>
            <strong>{{ item.value }}</strong>
            <span>{{ item.label }}</span>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { UserFilled } from "@element-plus/icons-vue";
import { MenuTypeEnum } from "@/enums/system/menu.enum";
import { useUserStore } from "@stores";

defineOptions({ name: "HomeBanner" });

type HomeUser = {
  avatar: string;
  name: string;
  username: string;
  description: string;
  last_login: string;
};

const fallbackUser: HomeUser = {
  avatar: "",
  name: "当前用户",
  username: "-",
  description: "系统后台用户",
  last_login: "",
};

const userStore = useUserStore();

const currentUser = computed<HomeUser>(() => {
  const userInfo = userStore.basicInfo;

  return {
    avatar: userInfo.avatar || fallbackUser.avatar,
    name: userInfo.name || fallbackUser.name,
    username: userInfo.username || fallbackUser.username,
    description: userInfo.description || fallbackUser.description,
    last_login: userInfo.last_login || fallbackUser.last_login,
  };
});

const bannerTitle = "知识库工作台";
const bannerSubtitle = computed(
  () => `${currentUser.value.name}，从知识库、文档、检索和员工权限开始今天的维护。`
);
const knowledgeMenuCount = computed(() => {
  const knowledgeRoot = userStore.getRouteList.find(
    (menu) => menu.route_name === "AI" || menu.route_path === "/ai"
  );
  return (
    knowledgeRoot?.children?.filter(
      (menu) => menu.type !== MenuTypeEnum.BUTTON && !menu.hidden
    ).length ?? 0
  );
});
const permissionCount = computed(() => userStore.getPerms.length);

const statusCards = computed(() => [
  {
    label: "认证会话",
    value: userStore.isLogin ? "已登录" : "未登录",
    icon: "ri:shield-user-line",
    tone: userStore.isLogin ? "cyan" : "amber",
  },
  {
    label: "知识库入口",
    value: `${knowledgeMenuCount.value} 个`,
    icon: "ri:layout-grid-line",
    tone: "blue",
  },
  {
    label: "权限点",
    value: `${permissionCount.value} 项`,
    icon: "ri:key-2-line",
    tone: "green",
  },
]);

</script>

<style scoped lang="scss">
.home-command-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
  gap: 24px;
  min-height: 204px;
  padding: 28px 32px;
  color: var(--el-text-color-primary);
  background: var(--fa-color-surface, var(--el-bg-color));
  border: 1px solid var(--fa-color-border, var(--el-border-color));
  border-radius: 8px;
}

.hero-copy,
.hero-status-panel {
  min-width: 0;
}

.hero-kicker {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.signal-dot,
.panel-dot {
  width: 8px;
  height: 8px;
  background: var(--el-color-success);
  border-radius: 50%;
}

h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 760;
  line-height: 1.25;
  color: var(--el-text-color-primary);
}

p {
  max-width: 680px;
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}

.operator-card {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 24px;
}

.operator-avatar {
  flex: 0 0 48px;
  background: transparent;
}

.operator-avatar--fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 8px;
}

.operator-meta {
  display: grid;
  min-width: 0;
}

.operator-meta strong {
  color: var(--el-text-color-primary);
}

.operator-meta span,
.operator-login {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.operator-login {
  margin-left: auto;
  white-space: nowrap;
}

.hero-status-panel {
  align-self: center;
  padding: 14px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.status-panel-head {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.hero-status-grid {
  display: grid;
  gap: 8px;
}

.status-chip {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 46px;
  padding: 8px 10px;
  background: var(--fa-color-surface, var(--el-bg-color));
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
}

.status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
}

.status-icon--cyan,
.status-icon--green {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.status-icon--blue {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.status-icon--amber {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}

.status-chip div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.status-chip strong {
  color: var(--el-text-color-primary);
}

.status-chip span:last-child {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (width <= 900px) {
  .home-command-hero {
    grid-template-columns: 1fr;
    padding: 24px;
  }

  .operator-login {
    margin-left: 0;
  }
}

@media (width <= 560px) {
  .home-command-hero {
    padding: 20px;
  }

  h1 {
    font-size: 24px;
  }

  .operator-card {
    flex-wrap: wrap;
    align-items: flex-start;
  }

  .operator-login {
    flex-basis: 100%;
    margin-left: 60px;
  }
}
</style>

<style scoped lang="scss">
.home-command-hero {
  position: relative;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.72fr);
  gap: 40px;
  min-height: 252px;
  padding: 32px;
  overflow: hidden;
  color: #f3fbf8;
  background:
    radial-gradient(circle at 78% 18%, rgb(45 125 114 / 24%), transparent 36%),
    linear-gradient(
      120deg,
      var(--fa-color-sidebar) 0%,
      color-mix(in srgb, var(--fa-color-sidebar) 72%, var(--fa-color-accent)) 100%
    );
  border-color: color-mix(in srgb, var(--fa-color-accent) 34%, var(--fa-color-sidebar));
  border-radius: 10px;
}

.home-command-hero::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
  background:
    repeating-linear-gradient(90deg, rgb(255 255 255 / 5%) 0 1px, transparent 1px 68px),
    repeating-linear-gradient(0deg, rgb(255 255 255 / 4%) 0 1px, transparent 1px 68px);
  opacity: 0.6;
  mask-image: linear-gradient(90deg, black 0%, transparent 82%);
}

.home-command-hero::after {
  position: absolute;
  right: 22%;
  bottom: -170px;
  width: 420px;
  height: 420px;
  pointer-events: none;
  content: "";
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: 50%;
  box-shadow: 0 0 0 36px rgb(255 255 255 / 3%), 0 0 0 72px rgb(255 255 255 / 2%);
}

.hero-grid-mark {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.hero-grid-mark__label {
  position: absolute;
  bottom: 28px;
  left: 32px;
  font-family: var(--fa-font-mono, ui-monospace, monospace);
  font-size: 12px;
  font-weight: 700;
  color: rgb(243 251 248 / 86%);
}

.hero-grid-mark__ring {
  position: absolute;
  right: 22%;
  bottom: -170px;
  display: block;
  border: 1px solid rgb(255 255 255 / 10%);
  border-radius: 50%;
}

.hero-grid-mark__ring--large {
  width: 420px;
  height: 420px;
  box-shadow: 0 0 0 36px rgb(255 255 255 / 3%), 0 0 0 72px rgb(255 255 255 / 2%);
}

.hero-grid-mark__ring--small {
  right: calc(22% + 58px);
  bottom: -112px;
  width: 260px;
  height: 260px;
  border-color: rgb(132 231 179 / 15%);
}

.hero-copy,
.hero-status-panel {
  position: relative;
  z-index: 1;
}

.hero-kicker {
  gap: 10px;
  margin-bottom: 16px;
  font-family: var(--fa-font-mono, ui-monospace, monospace);
  font-size: 11px;
  color: #a8efe0;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.hero-kicker__index {
  color: rgb(243 251 248 / 76%);
}

.signal-dot,
.panel-dot {
  width: 7px;
  height: 7px;
  background: #84e7b3;
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(132 231 179 / 12%);
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(30px, 4vw, 46px);
  font-weight: 760;
  line-height: 1.12;
  color: #fff;
  letter-spacing: -0.04em;
}

.hero-title-mark {
  margin-left: 5px;
  color: #84e7b3;
}

.hero-copy > p {
  max-width: 620px;
  margin: 14px 0 0;
  font-size: 14px;
  line-height: 1.7;
  color: rgb(243 251 248 / 72%);
}

.operator-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding-top: 20px;
  margin-top: 28px;
  border-top: 1px solid rgb(255 255 255 / 12%);
}

.operator-avatar--fallback {
  color: #a8efe0;
  background: rgb(132 231 179 / 12%);
  border-color: rgb(132 231 179 / 25%);
}

.operator-meta {
  gap: 4px;
}

.operator-meta strong {
  color: #fff;
}

.operator-meta span,
.operator-login span {
  margin-top: 0;
  font-size: 12px;
  color: rgb(243 251 248 / 60%);
}

.operator-login {
  display: grid;
  gap: 4px;
  margin: 0;
  text-align: right;
}

.operator-login strong {
  font-size: 12px;
  font-weight: 600;
  color: rgb(243 251 248 / 86%);
}

.hero-status-panel {
  align-self: stretch;
  padding: 16px;
  background: rgb(7 19 24 / 30%);
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 8px;
}

.status-panel-head {
  justify-content: space-between;
  margin-bottom: 16px;
  color: #fff;
}

.status-panel-head__title {
  display: inline-flex;
  gap: 9px;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
}

.status-panel-head__code {
  font-family: var(--fa-font-mono, ui-monospace, monospace);
  font-size: 9px;
  color: rgb(243 251 248 / 50%);
  letter-spacing: 0.08em;
}

.hero-status-grid {
  gap: 8px;
}

.status-chip {
  min-height: 50px;
  padding: 8px 10px;
  background: rgb(255 255 255 / 7%);
  border-color: rgb(255 255 255 / 12%);
  border-radius: 6px;
}

.status-icon--cyan,
.status-icon--green {
  color: #84e7b3;
  background: rgb(132 231 179 / 13%);
}

.status-icon--blue {
  color: #9ad8ff;
  background: rgb(154 216 255 / 13%);
}

.status-icon--amber {
  color: #f4ca76;
  background: rgb(244 202 118 / 13%);
}

.status-chip strong {
  color: #fff;
}

.status-chip span:last-child {
  color: rgb(243 251 248 / 58%);
}

@media (width <= 900px) {
  .home-command-hero {
    grid-template-columns: 1fr;
    gap: 28px;
  }

  .hero-status-panel {
    align-self: auto;
  }
}

@media (width <= 560px) {
  .home-command-hero {
    padding: 22px;
  }

  .hero-copy h1 {
    font-size: 32px;
  }

  .hero-grid-mark__label {
    bottom: 22px;
    left: 22px;
  }

  .operator-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .operator-login {
    grid-column: 2;
    text-align: left;
  }

  .status-panel-head__code {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-command-hero::after {
    box-shadow: none;
  }
}
</style>

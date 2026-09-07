<!-- 登录页：顶栏固定；仅插画列与表单区随布局切换 -->
<template>
  <div class="login-page-root flex h-screen w-full flex-col overflow-hidden">
    <FaLoginCenterBackdrop v-if="panelAlign === 'center'" viewport-fixed />
    <FaAuthTopBar v-model:panel-align="panelAlign" />

    <div
      class="login-auth-split relative z-1 flex min-h-0 flex-1 overflow-hidden"
      :class="`login-auth-split--${panelAlign}`"
    >
      <div
        v-if="panelAlign !== 'center'"
        class="login-auth-split__col login-auth-split__col--illustration"
      >
        <FaEnterpriseIntro />
      </div>

      <div
        class="login-auth-split__col login-auth-split__col--form login-page-panel relative flex min-h-0 min-w-0 flex-col"
        :class="panelAlign === 'center' ? 'bg-transparent' : 'bg-(--el-bg-color-page)'"
      >
        <div
          class="login-page-panel__main relative z-1 flex min-h-0 flex-1 flex-col overflow-hidden px-5 pb-2 pt-14 md:px-10 md:pt-18"
        >
          <ElScrollbar>
            <div
              class="login-page-panel__scroll pb-6"
              :class="panelAlign === 'center' && 'login-page-panel__scroll--centered'"
            >
              <div
                class="login-panel-align-row flex w-full items-center justify-center max-sm:min-h-0"
                :class="
                  panelAlign === 'center'
                    ? 'min-h-0 flex-1 py-4'
                    : 'min-h-[min(720px,calc(100vh-13rem))]'
                "
              >
                <div class="auth-right-wrap">
                  <div class="form">
                    <div class="form-intro">
                      <h3 class="title">{{ panelTitle }}</h3>
                      <p class="sub-title">{{ panelSubTitle }}</p>
                    </div>

                    <template v-if="setupMode">
                      <ElForm
                        ref="cloudConfigFormRef"
                        :model="cloudConfigForm"
                        :rules="cloudConfigRules"
                        label-position="top"
                        @submit.prevent="handleCloudConfigSubmit"
                      >
                        <ElFormItem :label="cloudConfigUsernameLabel" prop="admin_username">
                          <ElInput
                            v-model="cloudConfigForm.admin_username"
                            autocomplete="username"
                            :placeholder="t('login.placeholder.username')"
                          />
                        </ElFormItem>
                        <ElFormItem :label="cloudConfigPasswordLabel" prop="admin_password">
                          <ElInput
                            v-model="cloudConfigForm.admin_password"
                            type="password"
                            show-password
                            autocomplete="current-password"
                            :placeholder="t('login.placeholder.password')"
                          />
                        </ElFormItem>
                        <ElFormItem :label="t('login.cloudConfig.instanceId')" prop="instance_id">
                          <ElInputNumber
                            v-model="cloudConfigForm.instance_id"
                            :min="1"
                            :controls="false"
                            class="w-full"
                            :placeholder="t('login.cloudConfig.instanceIdPlaceholder')"
                          />
                        </ElFormItem>
                        <ElFormItem
                          :label="t('login.cloudConfig.serviceCredential')"
                          prop="service_credential"
                        >
                          <ElInput
                            v-model="cloudConfigForm.service_credential"
                            type="password"
                            show-password
                            autocomplete="new-password"
                            :placeholder="t('login.cloudConfig.serviceCredentialPlaceholder')"
                          />
                        </ElFormItem>
                        <ElButton
                          type="primary"
                          native-type="submit"
                          :loading="loading"
                          class="w-full"
                        >
                          {{ t("login.cloudConfig.submit") }}
                        </ElButton>
                      </ElForm>
                      <div class="mt-4 text-center">
                        <ElButton link type="primary" @click="showLoginMode">
                          {{ t("login.cloudConfig.back") }}
                        </ElButton>
                      </div>
                    </template>
                    <template v-else>
                      <FaLoginAccountForm
                        ref="accountFormRef"
                        v-model:login-form="loginForm"
                        :rules="rules"
                        :form-key="formKey"
                        :loading="loading"
                        :captcha-enabled="captchaEnabled"
                        :captcha-image="captchaImage"
                        :captcha-loading="captchaLoading"
                        @submit="handleSubmit"
                        @refresh-captcha="loadCaptcha(true)"
                      />
                      <div v-if="cloudConfigAvailable" class="mt-4 text-center">
                        <ElButton link type="primary" @click="showCloudConfigSetup">
                          {{
                            cloudConfigConfigured
                              ? t("login.cloudConfig.updateLink")
                              : t("login.cloudConfig.setupLink")
                          }}
                        </ElButton>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </ElScrollbar>
        </div>

        <footer
          class="login-page-footer login-page-footer--pinned shrink-0 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3"
          :class="panelAlign === 'center' && 'login-page-footer--floating-layout'"
        >
          <div class="login-footer-text text-sm">
            <div class="login-footer-row">
              <span>{{ footerCopyright }}</span>
            </div>
            <span class="login-page-footer__sep login-footer-sep-center">|</span>
            <div class="login-footer-row">
              <a
                :href="footerHelpDoc"
                target="_blank"
                rel="noopener noreferrer"
                class="login-page-footer__link"
              >
                帮助
              </a>
              <span class="login-page-footer__sep">|</span>
              <a
                :href="footerPrivacy"
                target="_blank"
                rel="noopener noreferrer"
                class="login-page-footer__link"
              >
                隐私
              </a>
              <span class="login-page-footer__sep">|</span>
              <a
                :href="footerClause"
                target="_blank"
                rel="noopener noreferrer"
                class="login-page-footer__link"
              >
                条款
              </a>
              <span v-if="footerKeepRecord" class="login-page-footer__sep">|</span>
              <span v-if="footerKeepRecord" class="login-page-footer__record">
                {{ footerKeepRecord }}
              </span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { LocationQuery, RouteLocationRaw } from "vue-router";
import type { CloudConfigBindForm, LoginFormData } from "@/api/module_system/auth";
import AuthAPI from "@/api/module_system/auth";
import { useConfigStore, useAppStore, useSettingsStore, useUserStore } from "@stores";
import { Auth, getConfigValue, HttpError } from "@utils";
import { ElNotification, type FormInstance, type FormRules } from "element-plus";
import FaLoginAccountForm from "@/components/views/fa-login/forms/FaLoginAccountForm.vue";
import FaAuthTopBar from "@/components/views/fa-login/widgets/FaAuthTopBar.vue";
import FaEnterpriseIntro from "@/components/views/fa-login/widgets/FaEnterpriseIntro.vue";
import { useLoginPanelAlign } from "@/components/views/fa-login/composables/useLoginPanelAlign";

defineOptions({ name: "Login" });

const configStore = useConfigStore();
const settingStore = useSettingsStore();
const appStore = useAppStore();
const { t, locale } = useI18n();

const { panelAlign } = useLoginPanelAlign();

const setupMode = ref(false);
const cloudConfigAvailable = ref(false);
const cloudConfigConfigured = ref(false);
const panelTitle = computed(() => {
  if (!setupMode.value) return t("login.title");
  return t(
    cloudConfigConfigured.value ? "login.cloudConfig.updateTitle" : "login.cloudConfig.title"
  );
});
const panelSubTitle = computed(() => {
  if (!setupMode.value) return t("login.subTitle");
  return t(
    cloudConfigConfigured.value ? "login.cloudConfig.updateSubTitle" : "login.cloudConfig.subTitle"
  );
});
const cloudConfigUsernameLabel = computed(() =>
  t(
    cloudConfigConfigured.value
      ? "login.cloudConfig.ownerUsername"
      : "login.cloudConfig.adminUsername"
  )
);
const cloudConfigPasswordLabel = computed(() =>
  t(
    cloudConfigConfigured.value
      ? "login.cloudConfig.ownerPassword"
      : "login.cloudConfig.adminPassword"
  )
);

const footerCopyright = computed(() =>
  getConfigValue(configStore.configData, ["copyright", "sys_web_copyright"])
);
const footerHelpDoc = computed(() =>
  getConfigValue(configStore.configData, ["help_doc", "sys_help_doc"], "#")
);
const footerPrivacy = computed(() =>
  getConfigValue(configStore.configData, ["privacy", "sys_web_privacy"], "#")
);
const footerClause = computed(() =>
  getConfigValue(configStore.configData, ["clause", "sys_web_clause"], "#")
);
const footerKeepRecord = computed(() =>
  getConfigValue(configStore.configData, ["keep_record", "sys_keep_record"])
);
const formKey = ref(0);

watch(locale, () => {
  formKey.value++;
});

const userStore = useUserStore();
const router = useRouter();
const route = useRoute();

const accountFormRef = ref<InstanceType<typeof FaLoginAccountForm> | null>(null);
const cloudConfigFormRef = ref<FormInstance | null>(null);
const loading = ref(false);

const loginForm = reactive<LoginFormData>({
  username: "",
  password: "",
  remember: true,
  login_type: "PC",
  captcha_key: "",
  captcha: "",
});

const captchaEnabled = ref(false);
const captchaImage = ref("");
const captchaLoading = ref(false);

const cloudConfigForm = reactive<CloudConfigBindForm>({
  admin_username: "",
  admin_password: "",
  instance_id: 0,
  service_credential: "",
});

const cloudConfigRules = computed<FormRules<CloudConfigBindForm>>(() => ({
  admin_username: [
    {
      required: true,
      message: t(
        cloudConfigConfigured.value
          ? "login.cloudConfig.ownerUsernameRequired"
          : "login.cloudConfig.adminUsernameRequired"
      ),
      trigger: "blur",
    },
  ],
  admin_password: [
    {
      required: true,
      message: t(
        cloudConfigConfigured.value
          ? "login.cloudConfig.ownerPasswordRequired"
          : "login.cloudConfig.adminPasswordRequired"
      ),
      trigger: "blur",
    },
  ],
  instance_id: [
    { required: true, message: t("login.cloudConfig.instanceIdRequired"), trigger: "change" },
    {
      type: "number",
      min: 1,
      message: t("login.cloudConfig.instanceIdRequired"),
      trigger: "change",
    },
  ],
  service_credential: [
    { required: true, message: t("login.cloudConfig.serviceCredentialRequired"), trigger: "blur" },
  ],
}));

async function loadCloudConfigStatus() {
  try {
    const response = await AuthAPI.getCloudConfigStatus();
    const data = response.data.data;
    cloudConfigAvailable.value = Boolean(data?.available);
    cloudConfigConfigured.value = Boolean(data?.configured);
  } catch {
    cloudConfigAvailable.value = false;
    cloudConfigConfigured.value = false;
  }
}

function showCloudConfigSetup() {
  setupMode.value = true;
  cloudConfigForm.admin_password = "";
  cloudConfigForm.service_credential = "";
}

function showLoginMode() {
  setupMode.value = false;
  cloudConfigFormRef.value?.resetFields();
}

async function handleCloudConfigSubmit() {
  if (!cloudConfigFormRef.value || !(await cloudConfigFormRef.value.validate())) return;

  const rebinding = cloudConfigConfigured.value;
  try {
    loading.value = true;
    await AuthAPI.bindCloudConfig({
      ...cloudConfigForm,
      instance_id: Number(cloudConfigForm.instance_id),
    });
    cloudConfigConfigured.value = true;
    setupMode.value = false;
    cloudConfigForm.admin_username = "";
    cloudConfigForm.admin_password = "";
    cloudConfigForm.instance_id = 0;
    cloudConfigForm.service_credential = "";
    ElNotification({
      title: t("login.cloudConfig.successTitle"),
      message: t(
        rebinding ? "login.cloudConfig.updateSuccess" : "login.cloudConfig.initialSuccess"
      ),
      type: "success",
    });
  } catch (error) {
    if (!(error instanceof HttpError)) {
      console.error("[Login] 云面板绑定失败:", error);
      ElNotification({
        title: t("login.cloudConfig.errorTitle"),
        message: t("login.cloudConfig.error"),
        type: "error",
      });
    }
  } finally {
    loading.value = false;
  }
}

/** Load a fresh login challenge and optionally reveal adaptive CAPTCHA. */
async function loadCaptcha(forceVisible = false) {
  captchaLoading.value = true;
  try {
    const response = await AuthAPI.getCaptcha();
    const data = response.data.data;
    captchaImage.value = data?.img_base || "";
    loginForm.captcha_key = data?.key || "";
    loginForm.captcha = "";
    captchaEnabled.value = forceVisible || Boolean(data?.enable);
  } catch (error) {
    console.warn("[Login] 获取验证码失败", error);
    if (forceVisible) captchaEnabled.value = true;
  } finally {
    captchaLoading.value = false;
  }
}

const rules = computed<FormRules>(() => {
  return {
    username: [
      {
        required: true,
        trigger: "blur",
        message: t("login.message.username.required"),
      },
    ],
    password: [
      {
        required: true,
        trigger: "blur",
        message: t("login.message.password.required"),
      },
      {
        min: 6,
        message: t("login.message.password.min"),
        trigger: "blur",
      },
    ],
    captcha: [
      {
        required: captchaEnabled.value,
        trigger: "blur",
        message: "请输入验证码",
      },
    ],
  };
});

function resolveRedirectTarget(query: LocationQuery): RouteLocationRaw {
  const defaultPath = "/";
  const rawRedirect = (query.redirect as string) || defaultPath;
  try {
    const resolved = router.resolve(rawRedirect);
    return {
      path: resolved.path,
      query: resolved.query,
    };
  } catch {
    return { path: defaultPath };
  }
}

async function consumeOAuthTicket(): Promise<boolean> {
  const ticket = typeof route.query.oauth_ticket === "string" ? route.query.oauth_ticket : "";
  if (!ticket) return false;

  const response = await AuthAPI.exchangeOAuthTicket({ ticket });
  const data = response.data.data;
  if (!data?.access_token || !data.refresh_token) {
    throw new Error("OAuth 登录凭证无效");
  }
  Auth.setTokens(data.access_token, data.refresh_token, true);
  userStore.setToken(data.access_token, data.refresh_token);
  await userStore.getUserInfo();
  await configStore.getConfig(true);
  userStore.setLoginStatus(true);
  const cleanQuery = { ...route.query };
  delete cleanQuery.oauth_ticket;
  await router.replace(resolveRedirectTarget(cleanQuery));
  return true;
}

onMounted(async () => {
  try {
    await configStore.getConfig(true);
    await loadCloudConfigStatus();
    if (await consumeOAuthTicket()) return;
    await loadCaptcha();
  } catch (error) {
    console.warn("[Login] 登录初始化失败，继续使用默认渲染", error);
    ElNotification({
      title: "登录失败",
      message: error instanceof Error ? error.message : "OAuth 登录凭证无效或已过期",
      type: "error",
    });
  }
  if (userStore.isLogin) {
    await router.replace(resolveRedirectTarget(route.query));
    return;
  }
});

const handleSubmit = async () => {
  if (!accountFormRef.value) return;

  try {
    const valid = await accountFormRef.value.validate?.();
    if (!valid) return;

    loading.value = true;

    await userStore.login(loginForm);
    await router.replace(resolveRedirectTarget(route.query));

    if (settingStore.showGuide) {
      appStore.showGuide(true);
    }
  } catch (error) {
    if (error instanceof HttpError && error.message.includes("验证码")) {
      await loadCaptcha(true);
    }
    if (!(error instanceof HttpError)) {
      console.error("[Login] Unexpected error:", error);
      ElNotification({
        title: "提示",
        message: error instanceof Error ? error.message : String(error),
        type: "error",
      });
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped lang="scss">
@use "../../../../components/views/fa-login/fa-login";
</style>

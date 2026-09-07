<template>
  <!-- 保持触发器为 inline-flex，让弹层锚点跟随头像尺寸。 -->
  <div class="fa-user-menu inline-flex shrink-0 items-center leading-none">
    <ElPopover
      ref="userMenuPopover"
      placement="bottom-end"
      :width="240"
      :hide-after="0"
      :offset="10"
      trigger="hover"
      :show-arrow="false"
      popper-class="user-menu-popover"
      popper-style="padding: 5px 16px;"
    >
      <template #reference>
        <div
          class="fa-user-menu__avatar-ref mr-5 max-sm:mr-[16px] cursor-pointer flex size-8.5 max-sm:w-6.5 max-sm:h-6.5 shrink-0 items-center justify-center"
        >
          <img
            v-if="userAvatar"
            class="size-full rounded-full object-cover block"
            :src="userAvatar"
            alt="avatar"
          />
          <img
            v-else
            class="size-full rounded-full block"
            src="@imgs/user/avatar.webp"
            alt="avatar"
          />
          <!-- 在线状态指示点。 -->
          <span class="fa-user-menu__online-dot" aria-hidden="true" />
        </div>
      </template>
      <template #default>
        <div class="pt-3">
          <div class="flex items-center pb-1 px-0">
            <img
              v-if="userAvatar"
              class="w-10 h-10 mr-3 ml-0 overflow-hidden rounded-full float-left object-cover"
              :src="userAvatar"
              alt=""
            />
            <img
              v-else
              class="w-10 h-10 mr-3 ml-0 overflow-hidden rounded-full float-left"
              src="@imgs/user/avatar.webp"
              alt=""
            />
            <div class="w-[calc(100%-60px)] h-full">
              <span class="block text-sm font-medium text-g-800 truncate">
                {{ displayName }}
              </span>
              <span class="block mt-0.5 text-xs text-g-500 truncate">{{ displayEmail }}</span>
            </div>
          </div>
          <ul class="py-4 mt-3 border-t border-g-300/80">
            <li
              class="flex items-center p-2 mb-3 select-none rounded-md cursor-pointer last:mb-0 hover:bg-(--fa-gray-200)"
              @click="openParamConfig"
            >
              <FaSvgIcon icon="ri:settings-3-line" class="mr-2 text-base" />
              <span class="text-sm">{{ $t("topBar.user.paramConfig") }}</span>
            </li>
            <li
              class="flex items-center p-2 mb-3 select-none rounded-md cursor-pointer last:mb-0 hover:bg-(--fa-gray-200)"
              @click="lockScreen()"
            >
              <FaSvgIcon icon="ri:lock-line" class="mr-2 text-base" />
              <span class="text-sm">{{ $t("topBar.user.lockScreen") }}</span>
            </li>
            <li class="mb-3 last:mb-0">
              <button
                type="button"
                class="flex w-full items-center p-2 select-none rounded-md cursor-pointer hover:bg-(--fa-gray-200) text-left"
                @click="openPasswordDialog"
              >
                <FaSvgIcon icon="ri:key-2-line" class="mr-2 text-base" />
                <span class="text-sm">{{ t("topBar.user.changePassword") }}</span>
              </button>
            </li>
            <div class="w-full h-px my-2 bg-g-300/80"></div>
            <li
              class="flex p-2 select-none rounded-md cursor-pointer last:mb-0 hover:bg-(--fa-gray-200) justify-center mt-5 mb-0 py-1.5 text-xs border border-g-400 hover:text-(--el-color-danger) hover:border-(--el-color-danger-light-3)"
              @click="handleLogout"
            >
              {{ $t("topBar.user.logout") }}
            </li>
          </ul>
        </div>
      </template>
    </ElPopover>

    <FaConfigInfoDrawer v-model="paramDrawerVisible" />
    <FaDialog
      v-model="passwordDialogVisible"
      append-to-body
      width="460px"
      :title="t('topBar.user.changePassword')"
      :confirm-loading="passwordSaving"
      form-mode="update"
      :confirm-text="t('common.confirm')"
      :cancel-text="t('common.cancel')"
      @confirm="submitPasswordChange"
      @cancel="closePasswordDialog"
      @close="resetPasswordForm"
    >
      <ElForm
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-position="top"
        @submit.prevent="submitPasswordChange"
      >
        <p class="mb-4 text-xs text-g-500">{{ t("topBar.user.passwordChangeHint") }}</p>
        <ElFormItem :label="t('topBar.user.oldPassword')" prop="old_password">
          <ElInput
            v-model="passwordForm.old_password"
            type="password"
            show-password
            clearable
            autocomplete="current-password"
            :placeholder="t('common.inputText')"
            maxlength="128"
          />
        </ElFormItem>
        <ElFormItem :label="t('topBar.user.newPassword')" prop="new_password">
          <ElInput
            v-model="passwordForm.new_password"
            type="password"
            show-password
            clearable
            autocomplete="new-password"
            :placeholder="t('common.inputText')"
            maxlength="128"
          />
        </ElFormItem>
        <ElFormItem :label="t('topBar.user.confirmPassword')" prop="confirm_password">
          <ElInput
            v-model="passwordForm.confirm_password"
            type="password"
            show-password
            clearable
            autocomplete="new-password"
            :placeholder="t('common.inputText')"
            maxlength="128"
          />
        </ElFormItem>
      </ElForm>
    </FaDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { useRouter } from "vue-router";
import { UserAPI, type PasswordFormState } from "@/api/module_system/user";
import { useUserStore } from "@stores";
import { mittBus } from "@utils";

defineOptions({ name: "FaUserMenu" });

const { t } = useI18n();
const userStore = useUserStore();
const router = useRouter();

const { info: userInfo } = storeToRefs(userStore);
const userMenuPopover = ref();
const paramDrawerVisible = ref(false);
const passwordDialogVisible = ref(false);
const passwordSaving = ref(false);
const passwordFormRef = ref<FormInstance>();
const passwordForm = reactive<PasswordFormState>({
  old_password: "",
  new_password: "",
  confirm_password: "",
});

const passwordRules = computed<FormRules>(() => ({
  old_password: [{ required: true, message: t("common.required"), trigger: "blur" }],
  new_password: [
    { required: true, message: t("common.required"), trigger: "blur" },
    { min: 6, max: 128, message: t("common.lengthRange", { min: 6, max: 128 }), trigger: "blur" },
  ],
  confirm_password: [
    { required: true, message: t("common.required"), trigger: "blur" },
    {
      validator: (_rule, value, callback) => {
        callback(value === passwordForm.new_password ? undefined : new Error(t("common.isEqual")));
      },
      trigger: "blur",
    },
  ],
}));

const userAvatar = computed(() => {
  const a = (userInfo.value as { avatar?: string })?.avatar?.trim();
  return a || "";
});

const displayName = computed(
  () =>
    (userInfo.value as { name?: string; username?: string })?.name ||
    (userInfo.value as { username?: string })?.username ||
    "-"
);

const displayEmail = computed(() => (userInfo.value as { email?: string })?.email || "");

function openParamConfig(): void {
  closeUserMenu();
  paramDrawerVisible.value = true;
}

function openPasswordDialog(): void {
  closeUserMenu();
  passwordDialogVisible.value = true;
}

function resetPasswordForm(): void {
  passwordForm.old_password = "";
  passwordForm.new_password = "";
  passwordForm.confirm_password = "";
  passwordFormRef.value?.clearValidate();
}

function closePasswordDialog(): void {
  passwordDialogVisible.value = false;
  resetPasswordForm();
}

async function submitPasswordChange(): Promise<void> {
  const valid = await passwordFormRef.value?.validate().catch(() => false);
  if (!valid || passwordSaving.value) return;

  passwordSaving.value = true;
  try {
    await UserAPI.changeCurrentUserPassword(passwordForm);
    ElMessage.success(t("topBar.user.passwordChanged"));
    passwordDialogVisible.value = false;
    resetPasswordForm();
    userStore.resetAllState();
    await router.replace({ name: "Login" });
  } finally {
    passwordSaving.value = false;
  }
}

function lockScreen(): void {
  mittBus.emit("openLockScreen");
}

function handleLogout(): void {
  closeUserMenu();
  setTimeout(async () => {
    try {
      await ElMessageBox.confirm(t("common.logoutTips"), t("common.tips"), {
        confirmButtonText: t("common.confirm"),
        cancelButtonText: t("common.cancel"),
        customClass: "login-out-dialog",
      });
      await userStore.logout();
    } catch {
      // 用户取消登出。
    }
  }, 200);
}

function closeUserMenu(): void {
  setTimeout(() => {
    userMenuPopover.value?.hide?.();
  }, 100);
}
</script>

<style scoped>
/* ElPopover 会用 tooltip trigger 包裹 reference，这里保持 inline-flex 以稳定对齐。 */
.fa-user-menu .el-tooltip__trigger {
  display: inline-flex !important;
  align-items: center;
  line-height: 1;
}

/* 头像引用元素负责在线状态点定位，并保持固定按钮尺寸。 */
.fa-user-menu__avatar-ref {
  position: relative;
  box-sizing: border-box;
}

.fa-user-menu__online-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 1;
  width: 8px;
  height: 8px;
  pointer-events: none;
  background-color: var(--el-color-success);
  border-radius: 50%;
  box-shadow: 0 0 2px rgb(0 0 0 / 20%);
}
</style>

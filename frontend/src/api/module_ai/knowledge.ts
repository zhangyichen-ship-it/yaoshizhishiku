import { request } from "@utils";

const API_PATH = "/ai/knowledge";

const KnowledgeAPI = {
  listKnowledgeBase(query: KnowledgeBaseListQuery) {
    return request<ApiResponse<PageResult<KnowledgeBase>>>({
      url: `${API_PATH}/list`,
      method: "get",
      params: query,
    });
  },

  createKnowledgeBase(body: KnowledgeBaseForm) {
    return request<ApiResponse<KnowledgeBase>>({
      url: `${API_PATH}/create`,
      method: "post",
      data: body,
    });
  },

  updateKnowledgeBase(id: number, body: KnowledgeBaseForm) {
    return request<ApiResponse<KnowledgeBase>>({
      url: `${API_PATH}/update/${id}`,
      method: "put",
      data: body,
    });
  },

  optionselect() {
    return request<ApiResponse<KnowledgeBase[]>>({
      url: `${API_PATH}/optionselect`,
      method: "get",
    });
  },

  deleteKnowledgeBase(body: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/delete`,
      method: "delete",
      data: body,
    });
  },

  listDocument(query: KnowledgeDocumentListQuery) {
    return request<ApiResponse<PageResult<KnowledgeDocument>>>({
      url: `${API_PATH}/document/list`,
      method: "get",
      params: query,
    });
  },

  uploadDocument(body: FormData) {
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${API_PATH}/document/upload`,
      method: "post",
      headers: { "Content-Type": "multipart/form-data" },
      data: body,
    });
  },

  reindexDocument(id: number) {
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${API_PATH}/document/${id}/reindex`,
      method: "post",
      showSuccessMessage: false,
    });
  },

  deleteDocument(body: number[]) {
    return request<ApiResponse>({
      url: `${API_PATH}/document/delete`,
      method: "delete",
      data: body,
    });
  },

  testRetrieval(body: RetrievalTestForm) {
    return request<ApiResponse<RetrievalTestResult>>({
      url: `${API_PATH}/retrieval/test`,
      method: "post",
      data: body,
    });
  },

  listMembers() {
    return request<ApiResponse<KbMember[]>>({
      url: `${API_PATH}/members`,
      method: "get",
    });
  },

  createMember(body: KbMemberCreateForm) {
    return request<ApiResponse<KbMember>>({
      url: `${API_PATH}/members`,
      method: "post",
      data: body,
      headers: { "Idempotency-Key": `kb-member-${body.username}` },
    });
  },

  updateMember(userId: number, body: KbMemberUpdateForm) {
    return request<ApiResponse<KbMember>>({
      url: `${API_PATH}/members/${userId}`,
      method: "patch",
      data: body,
    });
  },

  getMemberAccess(userId: number) {
    return request<ApiResponse<KnowledgeBaseAccess>>({
      url: `${API_PATH}/members/${userId}/access`,
      method: "get",
    });
  },

  setMemberAccess(userId: number, body: KnowledgeBaseAccessForm) {
    return request<ApiResponse<KnowledgeBaseAccess>>({
      url: `${API_PATH}/members/${userId}/access`,
      method: "put",
      data: body,
    });
  },

  getModelUsageSummary() {
    return request<ApiResponse<ModelUsageSummary>>({
      url: `${API_PATH}/usage-summary`,
      method: "get",
      showErrorMessage: false,
    });
  },

  getBillingSummary() {
    return request<ApiResponse<ModelBillingSummary>>({
      url: `${API_PATH}/billing-summary`,
      method: "get",
      showErrorMessage: false,
    });
  },
};

export default KnowledgeAPI;

export interface KnowledgeBaseListQuery extends PageQuery {
  name?: string;
  is_enabled?: boolean;
}

export interface KnowledgeBaseForm {
  name: string;
  description?: string | null;
  is_enabled: boolean;
}

export interface KnowledgeBase extends BaseType, KnowledgeBaseForm {
  document_count: number;
  indexed_document_count: number;
  indexing_document_count: number;
  failed_document_count: number;
}

export interface KnowledgeDocumentListQuery extends PageQuery {
  knowledge_base_id?: number;
  file_name?: string;
  parse_status?: string;
  index_status?: string;
}

export interface KnowledgeDocument extends BaseType {
  knowledge_base_id: number;
  file_name: string;
  file_path?: string | null;
  file_type: string;
  file_size: number;
  parse_status: string;
  index_status: string;
  error_message?: string | null;
  chunk_count: number;
}

export interface RetrievalTestForm {
  query: string;
  knowledge_base_ids: number[];
  top_k: number;
}

export interface RetrievalHit {
  content: string;
  metadata: Record<string, unknown>;
  distance?: number;
  score?: number;
}

export interface RetrievalTestResult {
  query: string;
  retrieval_mode: "vector" | "bm25" | "hybrid";
  results: RetrievalHit[];
}

export interface KbMember {
  user_id: number;
  username: string;
  name: string;
  email?: string | null;
  status: number;
  knowledge_enabled: boolean;
  local_role: string;
  knowledge_base_ids: number[];
}

export interface KbMemberCreateForm {
  username: string;
  password: string;
  name: string;
  email?: string;
  status: number;
  desktop_enabled: boolean;
  knowledge_enabled: boolean;
  model_enabled: boolean;
}

export type KbMemberUpdateForm = Partial<Omit<KbMemberCreateForm, "username" | "password">>;

export interface KnowledgeBaseAccess {
  user_id: number;
  knowledge_base_ids: number[];
}

export interface KnowledgeBaseAccessForm {
  knowledge_base_ids: number[];
}

export interface ModelUsageDay {
  day: string;
  request_count: number;
  usage_reported_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  total_cost_cny: number;
  free_cost_cny: number;
  paid_cost_cny: number;
}

export interface ModelUsageUser {
  user_id: string | null;
  username: string;
  request_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  total_cost_cny: number;
  free_cost_cny: number;
  paid_cost_cny: number;
}

export interface ModelUsageSummary {
  items: ModelUsageDay[];
  users?: ModelUsageUser[];
  request_count: number;
  usage_reported_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  cache_creation_input_tokens: number;
  total_cost_cny: number;
  free_cost_cny: number;
  paid_cost_cny: number;
}

export interface ModelBillingSummary {
  currency: "CNY";
  memberCount: number;
  freeLimitCny: number;
  freeUsedCny: number;
  freeRemainingCny: number;
  paidBalanceCny: number;
  totalAvailableCny: number;
  billingBlocked: boolean;
}

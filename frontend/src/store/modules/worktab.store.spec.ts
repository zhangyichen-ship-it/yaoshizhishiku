import { describe, expect, it, vi } from "vitest";

vi.mock("@/router", () => ({ router: {} }));
vi.mock("@/hooks/core/useCommon", () => ({ useCommon: () => ({}) }));
vi.mock("@/router/staticRoutes", () => ({ ROUTE_PATH_LOGIN_ALT: "/auth/login" }));

import { isConcreteWorktabRoute } from "./worktab.store";

describe("isConcreteWorktabRoute", () => {
  it("does not treat the 404 catch-all as an existing business route", () => {
    expect(isConcreteWorktabRoute({ name: "CatchAll404", path: "/:pathMatch(.*)*" })).toBe(false);
    expect(isConcreteWorktabRoute({ path: "/:pathMatch(.*)*" })).toBe(false);
    expect(isConcreteWorktabRoute({ name: "Knowledge", path: "/ai/knowledge" })).toBe(true);
  });
});

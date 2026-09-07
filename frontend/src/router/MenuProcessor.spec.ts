import { describe, expect, it } from "vitest";

import { backendMenusToAppRoutes } from "./menuRoutes";

describe("backendMenusToAppRoutes", () => {
  it("keeps button permissions out of dynamic routes", () => {
    const routes = backendMenusToAppRoutes([
      {
        id: 1,
        name: "系统管理",
        type: 1,
        route_name: "System",
        route_path: "/system",
        title: "系统管理",
        children: [
          {
            id: 2,
            name: "用户管理",
            type: 2,
            permission: "module_system:user:query",
            route_name: "User",
            route_path: "user",
            component_path: "module_system/user/index",
            title: "用户管理",
            children: [
              {
                id: 3,
                name: "新增",
                type: 3,
                permission: "module_system:user:create",
                title: "新增",
                route_name: "UserCreateButton",
                route_path: "create",
                component_path: "module_system/user/create",
              },
            ],
          },
        ],
      },
    ] as any);

    expect(JSON.stringify(routes)).toContain("用户管理");
    expect(JSON.stringify(routes)).not.toContain("UserCreateButton");
    expect(JSON.stringify(routes)).not.toContain("module_system/user/create");
  });

  it("does not promote descendants from a flat persisted menu list", () => {
    const routes = backendMenusToAppRoutes([
      {
        id: 1,
        name: "AI 知识库",
        type: 1,
        route_name: "AI",
        route_path: "/ai",
        title: "AI 知识库",
        children: [
          {
            id: 2,
            name: "知识库管理",
            type: 2,
            parent_id: 1,
            route_name: "Knowledge",
            route_path: "knowledge",
            component_path: "module_ai/knowledge/index",
            title: "知识库管理",
          },
        ],
      },
      {
        id: 2,
        name: "知识库管理",
        type: 2,
        parent_id: 1,
        route_name: "Knowledge",
        route_path: "knowledge",
        component_path: "module_ai/knowledge/index",
        title: "知识库管理",
      },
    ] as any);

    expect(routes.map((route) => route.name)).toEqual(["AI"]);
    expect(routes[0]?.children?.map((route) => route.name)).toEqual(["Knowledge"]);
  });
});

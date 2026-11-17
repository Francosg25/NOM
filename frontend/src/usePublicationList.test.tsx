import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import usePublicationList, { createPublicationCache } from "./usePublicationList";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const list = (title: string) => ({ total: 1, items: [{ id: 1, title }] });

describe("publication navigation", () => {
  it("shows the saved tab synchronously while checking for newer publications", async () => {
    const nextNews = deferred<ReturnType<typeof list>>();
    const request = vi.fn().mockResolvedValueOnce(list("News"))
      .mockResolvedValueOnce(list("Catalogue")).mockReturnValueOnce(nextNews.promise);
    const { result, rerender } = renderHook(({ key }) => usePublicationList(request, true, key, 0, null),
      { initialProps: { key: "news" } });
    await waitFor(() => expect(result.current.items[0]?.title).toBe("News"));
    rerender({ key: "catalogue" });
    expect(result.current.items).toEqual([]);
    expect(result.current.busy).toBe(true);
    await waitFor(() => expect(result.current.items[0]?.title).toBe("Catalogue"));
    rerender({ key: "news" });
    expect(result.current.items[0].title).toBe("News");
    expect(result.current.busy).toBe(false);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    await act(async () => nextNews.resolve(list("New publication")));
    expect(result.current.items[0].title).toBe("New publication");
  });

  it("never applies a late response to a different filter and aborts obsolete searches", async () => {
    const old = deferred<ReturnType<typeof list>>();
    let signal: AbortSignal | undefined;
    const request = vi.fn((key: string, _method?: string, _body?: unknown, s?: AbortSignal) => {
      if (key === "filter=old") { signal = s; return old.promise; }
      return Promise.resolve(list(key));
    });
    const { result, rerender } = renderHook(({ key }) => usePublicationList(request, true, key, 0, null),
      { initialProps: { key: "filter=old" } });
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
    rerender({ key: "filter=new&page=2" });
    await waitFor(() => expect(result.current.items[0]?.title).toBe("filter=new&page=2"));
    expect(signal?.aborted).toBe(true);
    await act(async () => old.resolve(list("Obsolete response")));
    expect(result.current.items[0].title).toBe("filter=new&page=2");
  });

  it("does not reuse another authenticated session's cached results", async () => {
    const first = vi.fn().mockResolvedValue(list("First session"));
    const next = deferred<ReturnType<typeof list>>();
    const second = vi.fn().mockReturnValue(next.promise);
    const { result, rerender } = renderHook(({ request }) => usePublicationList(request, true, "same-list", 0, null),
      { initialProps: { request: first } });
    await waitFor(() => expect(result.current.items[0]?.title).toBe("First session"));
    rerender({ request: second });
    expect(result.current.items).toEqual([]);
    expect(result.current.busy).toBe(true);
    await waitFor(() => expect(second).toHaveBeenCalledOnce());
    await act(async () => next.resolve(list("Second session")));
    expect(result.current.items[0].title).toBe("Second session");
  });

  it("keeps saved publications visible when a background update fails", async () => {
    const request = vi.fn().mockResolvedValueOnce(list("Saved document"))
      .mockRejectedValueOnce(new Error("Temporary service failure"));
    const { result } = renderHook(() => usePublicationList(request, true, "list", 0, null));
    await waitFor(() => expect(result.current.items).toHaveLength(1));
    await act(async () => result.current.refresh());
    expect(result.current.items[0].title).toBe("Saved document");
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBe("Temporary service failure");
  });
});

describe("publication cache", () => {
  it("shares a pending prefetch with navigation and refreshes stale entries", async () => {
    let now = 0;
    const response = deferred<ReturnType<typeof list>>();
    const request = vi.fn().mockReturnValueOnce(response.promise).mockResolvedValueOnce(list("Updated"));
    const cache = createPublicationCache(request, () => now);
    const preload = cache.load("catalogue");
    const navigate = cache.load("catalogue", true);
    expect(request).toHaveBeenCalledOnce();
    response.resolve(list("Catalogue"));
    expect(await preload).toEqual(await navigate);
    await cache.load("catalogue");
    expect(request).toHaveBeenCalledOnce();
    now = 31000;
    expect(await cache.load("catalogue")).toEqual(list("Updated"));
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("bounds cached pages and clears all filters on invalidation", async () => {
    const request = vi.fn().mockResolvedValue(list("Document"));
    const cache = createPublicationCache(request);
    for (let page = 1; page <= 13; page++) await cache.load(`page=${page}`);
    expect(cache.peek("page=1")).toBeUndefined();
    expect(cache.peek("page=13")).toEqual(list("Document"));
    cache.clear();
    expect(cache.peek("page=13")).toBeUndefined();
    await cache.load("page=13");
    expect(request).toHaveBeenCalledTimes(14);
  });
});

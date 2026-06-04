import assert from "node:assert/strict";
import test from "node:test";

import { buildCaseListQuery } from "../lib/api.ts";

test("buildCaseListQuery omits empty fields", () => {
  const query = buildCaseListQuery({
    risk_bucket: "critical",
    decision: "",
    review_status: "pending",
    page: 2,
    page_size: 10,
  });

  assert.equal(query, "?risk_bucket=critical&review_status=pending&page=2&page_size=10");
});

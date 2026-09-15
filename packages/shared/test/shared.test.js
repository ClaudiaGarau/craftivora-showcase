import { describe, expect, it } from "vitest";
import { allowedUploadTypes, shortNaturalReply } from "../src/index.js";
describe("shared contracts", () => { it("answers greetings naturally", () => expect(shortNaturalReply("  CIAO ")).toBe("Ciao!")); it("rejects executable MIME types", () => expect(allowedUploadTypes.has("application/x-msdownload")).toBe(false)); });
//# sourceMappingURL=shared.test.js.map
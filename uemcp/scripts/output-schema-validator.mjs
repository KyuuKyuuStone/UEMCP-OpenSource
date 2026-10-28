/**
 * 迷你 JSON Schema 校验器（draft-07 子集，零依赖）——仅供本仓库 tests/smoke 校验
 * tools/list 发布的 outputSchema 与 structuredContent（任务 4248c955-A 验收：
 * 成功/错误路径都不被客户端 schema 校验打回）。
 * 支持关键字：anyOf/oneOf、const、enum、type、properties、required、
 * additionalProperties（false|true|schema）、items、not、
 * $schema/description（忽略）。
 * 这是 SDK 客户端（AjvJsonSchemaValidator，strict:false）行为的保守近似：
 * 只接受本仓库 outputSchema 实际用到的关键字，子集之外的写法会被视为通过（宽松）。
 */

const TYPEOF = {
  string: (v) => typeof v === "string",
  number: (v) => typeof v === "number",
  integer: (v) => typeof v === "number" && Number.isInteger(v),
  boolean: (v) => typeof v === "boolean",
  object: (v) => typeof v === "object" && v !== null && !Array.isArray(v),
  array: (v) => Array.isArray(v),
  null: (v) => v === null,
};

function typeMatches(t, v) {
  if (t === "number") return TYPEOF.number(v) || TYPEOF.integer(v);
  const f = TYPEOF[t];
  return f ? f(v) : true; // 未知类型关键字：宽松
}

function isEmptySchema(s) {
  return s === true || s === undefined || (typeof s === "object" && s !== null && !Array.isArray(s) && Object.keys(s).length === 0);
}

/**
 * @returns {{ valid: boolean, errors: string[] }}
 */
export function validate(schema, value) {
  const errors = [];
  check(schema, value, "$", errors);
  return { valid: errors.length === 0, errors };
}

function check(schema, value, path, errors) {
  if (isEmptySchema(schema)) return;
  if (schema === false) {
    errors.push(`${path}: schema false`);
    return;
  }
  if (typeof schema !== "object" || schema === null || Array.isArray(schema)) return;

  if (Array.isArray(schema.anyOf)) {
    if (!schema.anyOf.some((s) => checkPure(s, value))) {
      errors.push(`${path}: does not match any anyOf branch`);
    }
    // 不提前返回：根 schema 可同时携带自身约束（type/properties/required/...）
  }
  if (Array.isArray(schema.oneOf)) {
    const matched = schema.oneOf.filter((s) => checkPure(s, value)).length;
    if (matched !== 1) errors.push(`${path}: matches ${matched} oneOf branches (need exactly 1)`);
  }
  if (schema.not !== undefined) {
    if (checkPure(schema.not, value)) {
      errors.push(`${path}: must NOT match the "not" schema`);
    }
  }
  if ("const" in schema) {
    if (JSON.stringify(value) !== JSON.stringify(schema.const)) {
      errors.push(`${path}: const mismatch (expected ${JSON.stringify(schema.const)})`);
    }
  }
  if (Array.isArray(schema.enum)) {
    if (!schema.enum.some((e) => JSON.stringify(e) === JSON.stringify(value))) {
      errors.push(`${path}: enum mismatch`);
    }
  }
  if (schema.type !== undefined && schema.type !== null) {
    const ts = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!ts.some((t) => typeMatches(t, value))) {
      errors.push(`${path}: type ${JSON.stringify(schema.type)} expected, got ${typeof value}`);
      return;
    }
  }
  if (schema.items !== undefined && !Array.isArray(schema.items)) {
    if (Array.isArray(value)) {
      value.forEach((item, i) => check(schema.items, item, `${path}[${i}]`, errors));
    }
  }
  if (Array.isArray(schema.required) && typeof value === "object" && value !== null && !Array.isArray(value)) {
    for (const k of schema.required) {
      if (!(k in value)) errors.push(`${path}: missing required property "${k}"`);
    }
  }
  if (
    typeof value === "object" && value !== null && !Array.isArray(value) &&
    (schema.properties || schema.additionalProperties !== undefined)
  ) {
    const props = schema.properties ?? {};
    for (const [k, v] of Object.entries(value)) {
      if (k in props) {
        check(props[k], v, `${path}.${k}`, errors);
        continue;
      }
      const ap = schema.additionalProperties;
      if (ap === false) {
        errors.push(`${path}: additional property "${k}" not allowed`);
      } else if (ap === undefined || ap === true) {
        // 允许且不校验
      } else {
        check(ap, v, `${path}.${k}`, errors);
      }
    }
  }
}

/** 纯校验（不向 errors 追加，供 anyOf/oneOf 分支试配） */
function checkPure(schema, value) {
  const errs = [];
  check(schema, value, "$", errs);
  return errs.length === 0;
}

/** 提取工具 outputSchema 的成功/失败双分支（anyOf|oneOf，长度 2） */
export function outputSchemaBranches(tool) {
  const os = tool.outputSchema;
  if (!os || typeof os !== "object") return null;
  const branches = os.anyOf ?? os.oneOf;
  if (!Array.isArray(branches) || branches.length !== 2) return null;
  const success = branches.find((b) => b?.properties?.ok?.const === true);
  const failure = branches.find((b) => b?.properties?.ok?.const === false);
  if (!success || !failure) return null;
  return { success, failure };
}

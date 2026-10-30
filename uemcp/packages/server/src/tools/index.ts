import type { ToolDef } from "./common.js";
import { statusTool } from "./status.js";
import { actorQueryTool } from "./actorQuery.js";
import { actorEditTool } from "./actorEdit.js";
import { levelControlTool } from "./levelControl.js";
import { assetSearchTool } from "./assetSearch.js";
import { materialParamsTool } from "./materialParams.js";
import { viewportCaptureTool } from "./viewportCapture.js";
import { consoleCommandTool } from "./consoleCommand.js";
import { pythonExecTool } from "./pythonExec.js";
import { blueprintTool } from "./blueprint.js";
import { pieControlTool } from "./pieControl.js";
import { policyExplainTool } from "./policyExplain.js";
import { reflectTool } from "./reflect.js";
import { callFunctionTool } from "./callFunction.js";
import { logQueryTool } from "./logQuery.js";

export const ALL_TOOLS: ToolDef[] = [
  statusTool,
  actorQueryTool,
  actorEditTool,
  levelControlTool,
  assetSearchTool,
  materialParamsTool,
  viewportCaptureTool,
  consoleCommandTool,
  pythonExecTool,
  blueprintTool,
  pieControlTool,
  policyExplainTool,
  reflectTool,
  callFunctionTool,
  logQueryTool,
];

export type { ToolDef } from "./common.js";

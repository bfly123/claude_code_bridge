import { createCallAction, createGetActionResult } from "../../actions/utils.js";
import {
  computeCurrentLocale,
  computePreferredLocale,
  computePreferredLocaleList
} from "../../i18n/utils.js";
import { ASTRO_VERSION, clientAddressSymbol, clientLocalsSymbol } from "../constants.js";
import { AstroCookies } from "../cookies/index.js";
import { AstroError, AstroErrorData } from "../errors/index.js";
import { getClientIpAddress } from "../routing/request.js";
import { sequence } from "./sequence.js";
function defineMiddleware(fn) {
  return fn;
}
function createContext({
  request,
  params = {},
  userDefinedLocales = [],
  defaultLocale = ""
}) {
  let preferredLocale = void 0;
  let preferredLocaleList = void 0;
  let currentLocale = void 0;
  let clientIpAddress;
  const url = new URL(request.url);
  const route = url.pathname;
  const rewrite = (_reroutePayload) => {
    return Promise.resolve(new Response(null));
  };
  const context = {
    cookies: new AstroCookies(request),
    request,
    params,
    site: void 0,
    generator: `Astro v${ASTRO_VERSION}`,
    props: {},
    rewrite,
    redirect(path, status) {
      return new Response(null, {
        status: status || 302,
        headers: {
          Location: path
        }
      });
    },
    get preferredLocale() {
      return preferredLocale ??= computePreferredLocale(request, userDefinedLocales);
    },
    get preferredLocaleList() {
      return preferredLocaleList ??= computePreferredLocaleList(request, userDefinedLocales);
    },
    get currentLocale() {
      return currentLocale ??= computeCurrentLocale(route, userDefinedLocales, defaultLocale);
    },
    url,
    get clientAddress() {
      if (clientIpAddress) {
        return clientIpAddress;
      }
      clientIpAddress = getClientIpAddress(request);
      if (!clientIpAddress) {
        throw new AstroError(AstroErrorData.StaticClientAddressNotAvailable);
      }
      return clientIpAddress;
    },
    get locals() {
      let locals = Reflect.get(request, clientLocalsSymbol);
      if (locals === void 0) {
        locals = {};
        Reflect.set(request, clientLocalsSymbol, locals);
      }
      if (typeof locals !== "object") {
        throw new AstroError(AstroErrorData.LocalsNotAnObject);
      }
      return locals;
    },
    // We define a custom property, so we can check the value passed to locals
    set locals(val) {
      if (typeof val !== "object") {
        throw new AstroError(AstroErrorData.LocalsNotAnObject);
      } else {
        Reflect.set(request, clientLocalsSymbol, val);
      }
    }
  };
  return Object.assign(context, {
    getActionResult: createGetActionResult(context.locals),
    callAction: createCallAction(context)
  });
}
function isLocalsSerializable(value) {
  let type = typeof value;
  let plainObject = true;
  if (type === "object" && isPlainObject(value)) {
    for (const [, nestedValue] of Object.entries(value)) {
      if (!isLocalsSerializable(nestedValue)) {
        plainObject = false;
        break;
      }
    }
  } else {
    plainObject = false;
  }
  let result = value === null || type === "string" || type === "number" || type === "boolean" || Array.isArray(value) || plainObject;
  return result;
}
function isPlainObject(value) {
  if (typeof value !== "object" || value === null) return false;
  let proto = Object.getPrototypeOf(value);
  if (proto === null) return true;
  let baseProto = proto;
  while (Object.getPrototypeOf(baseProto) !== null) {
    baseProto = Object.getPrototypeOf(baseProto);
  }
  return proto === baseProto;
}
function trySerializeLocals(value) {
  if (isLocalsSerializable(value)) {
    return JSON.stringify(value);
  } else {
    throw new Error("The passed value can't be serialized.");
  }
}
export {
  createContext,
  defineMiddleware,
  sequence,
  trySerializeLocals
};

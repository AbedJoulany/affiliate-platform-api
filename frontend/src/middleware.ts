import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/services/session";

const PUBLIC_ROUTES = ["/login"];

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const signedIn = request.cookies.has(SESSION_COOKIE);
  if (!signedIn && !PUBLIC_ROUTES.includes(pathname)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};

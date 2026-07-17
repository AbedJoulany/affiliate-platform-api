"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button, Input } from "@/components/ui/primitives";
import { useLogin } from "../hooks/useAuth";

const loginSchema = z.object({
  email: z.string().email("أدخل بريدًا إلكترونيًا صحيحًا"),
  password: z.string().min(1, "كلمة المرور مطلوبة"),
});

type LoginValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const login = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  return (
    <form className="space-y-4" onSubmit={handleSubmit((values) => login.mutate(values))} noValidate>
      <div>
        <label className="mb-1.5 block text-sm font-medium" htmlFor="email">البريد الإلكتروني</label>
        <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
        {errors.email && <p className="mt-1 text-sm text-destructive">{errors.email.message}</p>}
      </div>
      <div>
        <label className="mb-1.5 block text-sm font-medium" htmlFor="password">كلمة المرور</label>
        <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register("password")} />
        {errors.password && <p className="mt-1 text-sm text-destructive">{errors.password.message}</p>}
      </div>
      {login.isError && (
        <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {login.error.message}
        </p>
      )}
      <Button className="w-full" loading={login.isPending} type="submit">تسجيل الدخول</Button>
    </form>
  );
}

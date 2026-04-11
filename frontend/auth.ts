import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      authorization: {
        params: {
          prompt: "consent",
          access_type: "offline",
          response_type: "code",
          scope: "openid profile email https://www.googleapis.com/auth/classroom.courses.readonly https://www.googleapis.com/auth/classroom.announcements.readonly https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly https://www.googleapis.com/auth/classroom.student-submissions.me.readonly https://www.googleapis.com/auth/classroom.student-submissions.students.readonly https://www.googleapis.com/auth/drive.readonly",
        },
      },
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
  ],
  callbacks: {
    async jwt({ token, account, user }) {
      // 1. First time logging in (we get 'account' and 'user' from Google)
      if (account && user) {
        // Send tokens to backend to store encryptly and get app JWT
        try {
          const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/store-tokens`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Secret": process.env.INTERNAL_API_SECRET ?? "",
            },
            body: JSON.stringify({
              user_id: user.id || token.sub,
              access_token: account.access_token,
              refresh_token: account.refresh_token,
              token_expiry: account.expires_at ? new Date(account.expires_at * 1000).toISOString() : null,
              email: user.email,
            }),
          });

          if (!response.ok) {
            console.error("Failed to store tokens in backend", await response.text());
          } else {
            const data = await response.json();
            // Store the backend's signed app JWT in the NextAuth JWT
            token.app_jwt = data.app_jwt;
          }
        } catch (error) {
          console.error("Error connecting to backend /api/store-tokens:", error);
        }
      }
      return token;
    },
    async session({ session, token }) {
      // Pass the app JWT to the client via session so `api.ts` can use it
      if (session.user) {
         session.app_jwt = token.app_jwt as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
});

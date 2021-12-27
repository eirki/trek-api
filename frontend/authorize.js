function redirect() {
  location.href = "/login.html";
}

export function checkLoggedinOrRedirect() {
  let token = localStorage.getItem("trekToken");
  if (!token) {
    console.log("no token, redirecting to login");
    redirect();
  } else {
    return token;
  }
}

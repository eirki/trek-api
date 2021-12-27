import { checkLoggedinOrRedirect } from "/authorize.js";

export function logout() {
  localStorage.removeItem("trekToken");
  checkLoggedinOrRedirect();
}

export async function addTracker(tracker_name) {
  let url = new URL("/user/add_tracker/" + tracker_name, location.href);
  const token = localStorage.getItem("trekToken");
  url.searchParams.set("redirect_url", location.origin + "/index.html");
  console.log(`Fetching ${url}`);
  await fetch(url, {
    method: "GET",
    headers: {
      Authorization: "Bearer " + token,
    },
  })
    .then((response) => response.json())
    .then((data) => (location.href = data.auth_url));
}

function makeTrekElem(trek_id, ownerList) {
  let url = new URL("/trek.html", location.origin);
  url.searchParams.set("id", trek_id);

  let trekElem = document.createElement("li");
  let a = document.createElement("a");
  a.href = url;
  a.innerHTML = `Trek ${trek_id}`;
  trekElem.appendChild(a);
  ownerList.appendChild(trekElem);
}
export function main() {
  const queryString = window.location.search;
  const urlParams = new URLSearchParams(queryString);
  let token = urlParams.get("jwt");
  if (token) {
    console.log("storing token");
    window.localStorage.setItem("trekToken", token);
    console.log("cleaning url");
    window.history.replaceState(
      null,
      document.title,
      location.origin + location.pathname
    );
  } else {
    token = checkLoggedinOrRedirect();

    let url = new URL("/user/me", location.href);
    console.log(`Fetching ${url}`);
    fetch(url, {
      method: "GET",
      headers: {
        Authorization: "Bearer " + token,
      },
    })
      .then((response) => response.json())
      .then((data) => {
        console.log(data);
        let element = document.getElementById("me");
        let stepsElem = document.createElement("div");
        stepsElem.innerHTML = `Steps yesterday: ${data.steps_data}`;
        element.appendChild(stepsElem);

        if (data.treks_owner_of.length > 0) {
          let ownerListElem = document.createElement("div");
          let ownerHeader = document.createElement("h3");
          ownerHeader.innerHTML = "Owner of ";
          ownerListElem.appendChild(ownerHeader);
          let ownerList = document.createElement("ul");
          data.treks_owner_of.map((trek_id) =>
            makeTrekElem(trek_id, ownerList)
          );
          ownerListElem.appendChild(ownerList);
          element.appendChild(ownerListElem);
        }
        if (data.treks_user_in.length > 0) {
          let userListElem = document.createElement("div");
          let userHeader = document.createElement("h3");
          userHeader.innerHTML = "Participating in";
          userListElem.appendChild(userHeader);
          let userList = document.createElement("ul");
          data.treks_user_in.map((trek_id) => makeTrekElem(trek_id, userList));
          userListElem.appendChild(userList);
          element.appendChild(userListElem);
        }
      });
  }
}

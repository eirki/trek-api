import { checkLoggedinOrRedirect } from "/authorize.js";

let state = {
  token: null,
  map: null,
  createElem: document.getElementById("createTrek"),
  route: null,
  start: {
    locations: null,
    selected: null,
    marker: null,
    skip: false,
  },
  stop: {
    locations: null,
    selected: null,
    marker: null,
  },
  via: [],
  selectLocation: (stateSubset, obj, searchBox) => {
    searchBox.input.value = obj.name;
    stateSubset.selected = obj;

    state.swapMarkers(stateSubset, [obj.latitude, obj.longitude]);
    state.updateBounds();
    state.updateRoute();
    state.updateCreateTrek();
  },
  updateBounds: () => {
    let markers = [state.start, ...state.via, state.stop]
      .filter((subset) => subset.marker)
      .map((subset) => subset.marker);
    var group = L.featureGroup(markers);
    state.map.fitBounds(group.getBounds());
  },
  swapMarkers: (subset, coords) => {
    if (subset.marker) {
      state.mapmap.removeLayer(subset.marker);
    }
    let marker = L.marker(coords).addTo(state.map);
    subset.marker = marker;
  },
  updateRoute: async () => {
    if (state.route) {
      state.map.removeLayer(state.route.elem);
    }

    if (!(state.start.selected && state.stop.selected)) {
      return;
    }

    let coords = (obj) => `${obj.latitude}, ${obj.longitude}`;
    let selectedVia = state.via.filter((subset) => subset.selected);
    let skipSegments = [state.start, ...selectedVia]
      .map((subset, index) => [subset.skip, index + 1])
      .filter(([skip, index]) => skip)
      .map(([skip, index]) => index);

    let route = await searchRoute(
      coords(state.start.selected),
      coords(state.stop.selected),
      selectedVia.map((subset) => coords(subset.selected)),
      skipSegments
    );

    if (!route) {
      state.route = null;
      return;
    }
    let routeElem = L.geoJSON(route.points).addTo(state.map);
    state.route = {
      waypoints: route.points.coordinates,
      distance: route.distance,
      elem: routeElem,
    };
  },
  updateCreateTrek: () => {
    state.createElem.hidden =
      state.start.selected === null || state.stop.selected === null;
  },
};

function makeMap(startAutocomp, stopAutocomp) {
  const tileServer = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attr =
    'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>';
  let map = L.map("mapid");
  L.tileLayer(tileServer, {
    attribution: attr,
    maxZoom: 15,
    id: "mapbox/streets-v11",
  }).addTo(map);
  map.setView([0, 0], 0);
  map.on("contextmenu", (event) => {
    let selected = {
      name: `${event.latlng.lat}, ${event.latlng.lng}`,
      latitude: event.latlng.lat,
      longitude: event.latlng.lng,
    };
    let popup = L.popup();
    let popupElem = document.createElement("div");

    let startBtn = document.createElement("button");
    startBtn.innerHTML = "Set as start";
    startBtn.addEventListener("click", (event) => {
      state.selectLocation(state.start, selected, startAutocomp);
      popup.removeFrom(map);
    });
    popupElem.appendChild(startBtn);

    let viaBtn = document.createElement("button");
    viaBtn.innerHTML = "Add as via";
    viaBtn.addEventListener("click", (event) => {
      let lastPlus =
        stopAutocomp.wrapper.parentElement.previousSibling.previousSibling.querySelector(
          "button"
        ); // wow!
      let index = state.via.length;
      let [stateSubset, autoComp] = makeVia(lastPlus, index);
      state.selectLocation(stateSubset, selected, autoComp);
      popup.removeFrom(map);
    });
    popupElem.appendChild(viaBtn);

    let stopBtn = document.createElement("button");
    stopBtn.innerHTML = "Set as stop";
    stopBtn.addEventListener("click", (event) => {
      state.selectLocation(state.stop, selected, stopAutocomp);
      popup.removeFrom(map);
    });
    popupElem.appendChild(stopBtn);

    popup.setLatLng(event.latlng).setContent(popupElem).addTo(map).openOn(map);
  });
  return map;
}

async function searchLocation(query, stateSubset) {
  let url = new URL("/search/locations", location.href);
  url.searchParams.set("query", query);
  console.log(`Fetching ${url}`);
  return await fetch(url, {
    method: "GET",
    headers: {
      Authorization: "Bearer " + state.token,
    },
  })
    .then((response) => response.json())
    .then((data) => {
      stateSubset.locations = data.locations;
      let locationNames = data.locations.map((location) => location.name);
      console.log(locationNames);
      return locationNames;
    });
}

async function searchRoute(start, stop, via, skipSegments) {
  let url = new URL("/search/route", location.href);
  var params = new URLSearchParams();
  params.append("start", start);
  params.append("stop", stop);
  via.forEach((loc) => params.append("via", loc));
  skipSegments.forEach((segment) => params.append("skip_segments", segment));
  url.search = new URLSearchParams(params).toString();

  console.log(`Fetching ${url}`);
  return await fetch(url, {
    method: "GET",
    headers: {
      Authorization: "Bearer " + state.token,
    },
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        return data.route;
      } else {
        window.alert(data.detail.error.message);
      }
    });
}

function makeAutocomplete(selector, stateSubset) {
  const searchBox = new autoComplete({
    searchEngine: (query, record) => record, // without this override, search by lat-lon will not work
    diacritics: true,
    selector: selector,
    placeHolder: "Search for Locations...",
    debounce: 500, // Milliseconds value
    data: {
      src: (query) => searchLocation(query, stateSubset),
    },
    resultsList: {
      element: (list, data) => {
        if (!data.results.length) {
          // Create "No Results" message element
          const message = document.createElement("div");
          // Add class to the created element
          message.setAttribute("class", "no_result");
          // Add message text content
          message.innerHTML = `<span>Found No Results for "${data.query}"</span>`;
          // Append message element to the results list
          list.prepend(message);
        }
      },
      noResults: true,
    },
    threshold: 3,
    resultItem: {
      highlight: true,
    },
    events: {
      input: {
        selection(event) {
          const index = event.detail.selection.index;
          let selected = stateSubset.locations[index];
          state.selectLocation(stateSubset, selected, searchBox);
        },
      },
    },
  });
  return searchBox;
}

export function makeVia(button, index) {
  let identifier = `autoComplete_${index}`;

  let wrapper = document.createElement("div");
  wrapper.innerHTML = "via";

  let elem = document.createElement("input");
  elem.setAttribute("id", identifier); // will not work with delete
  elem.setAttribute("type", "search");
  elem.setAttribute("spellcheck", "false");
  elem.setAttribute("autocorrect", "off");
  elem.setAttribute("autocomplete", "off");
  elem.setAttribute("autocapitalize", "off");
  wrapper.appendChild(elem);

  let stateSubset = {
    locations: null,
    selected: null,
    marker: null,
    elem: elem,
    skip: false,
  };

  let addBtn = document.createElement("button");
  addBtn.innerHTML = "+";
  addBtn.addEventListener("click", (event) => makeVia(event.target, index + 1));
  wrapper.appendChild(addBtn);

  let skipWrapper = document.createElement("div");
  let skipBtn = document.createElement("input");
  skipBtn.setAttribute("type", "checkbox");
  skipBtn.setAttribute("id", `checkbox_${identifier}`);
  skipBtn.addEventListener("change", (event) => {
    stateSubset.skip = event.target.checked;
    state.updateRoute();
  });
  let label = document.createElement("label");
  label.setAttribute("for", `checkbox_${identifier}`);
  skipWrapper.innerHTML = "Jump directly";
  skipWrapper.appendChild(skipBtn);
  skipWrapper.appendChild(label);
  wrapper.appendChild(skipWrapper);
  let parent = button.parentElement;
  parent.parentNode.insertBefore(wrapper, parent.nextSibling);

  state.via.splice(index, 0, stateSubset);
  let autoComp = makeAutocomplete("#" + identifier, stateSubset);
  return [stateSubset, autoComp];
}

export function checkJumpFirst(elem) {
  state.start.skip = elem.checked;
  state.updateRoute();
}

export function sendCreateTrek() {
  let url = new URL("/trek/", location.href);
  let data = {
    origin: state.start.selected.name,
    destination: state.stop.selected.name,
    waypoints: state.route.waypoints,
  };
  console.log(`Fetching ${url}`);
  fetch(url, {
    method: "POST",
    headers: {
      Authorization: "Bearer " + state.token,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })
    .then((response) => response.json())
    .then((data) => {
      let url = new URL("/trek.html", location.origin);
      url.searchParams.set("id", data.trek_id);
      location.href = url;
    });
}

export function main() {
  let token = checkLoggedinOrRedirect();
  state.token = token;

  let startAutocomp = makeAutocomplete("#autoComplete_start", state.start);
  let stopAutocomp = makeAutocomplete("#autoComplete_stop", state.stop);

  // leaflet
  let map = makeMap(startAutocomp, stopAutocomp);
  state.map = map;
}

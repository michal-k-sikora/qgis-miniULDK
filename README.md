# [PL] MiniULDK

**MiniULDK** to wtyczka do QGIS, która umożliwia **szybkie pobieranie działek ewidencyjnych bezpośrednio z poziomu mapy**.  
Działa z poziomu paska narzędziowego **OnGeo** - wystarczy włączyć narzędzie, kliknąć w wybrane miejsce na mapie, a wtyczka pobierze geometrię działki i doda ją do warstwy wynikowej w projekcie.

Wtyczka została przygotowana z myślą o prostym i szybkim wskazywaniu pojedynczych działek podczas codziennej pracy w QGIS.  
Dodatkowo może zapisywać pobierane działki do plików **SHP** lub **GPKG**, a także automatycznie przybliżać widok do wskazanej działki.

---

## Funkcje

Wtyczka umożliwia m.in.:

- pobieranie działki ewidencyjnej po kliknięciu na mapie,
- tworzenie warstwy wynikowej z pobranymi działkami w bieżącym projekcie,
- automatyczne policzenie powierzchni geometrycznej pobranej działki,
- zapisywanie wskazanych działek do plików **SHP**,
- zapisywanie wskazanych działek do pliku **GPKG**,
- opcjonalne dodawanie zapisanych warstw do projektu,
- opcjonalne automatyczne przybliżanie widoku do pobranej działki,
- anulowanie aktywnego narzędzia klawiszem **ESC**,
- zapamiętywanie ustawień w ramach projektu QGIS.

---

## Interfejs

Wtyczka udostępnia dwa główne elementy interfejsu:

### **1. Przycisk MiniULDK na pasku narzędzi OnGeo**
Służy do uruchomienia narzędzia wskazywania działek na mapie.  
Po kliknięciu przycisku możesz wskazywać działki bezpośrednio w oknie mapy.

![MiniULDK_1](https://github.com/michal-k-sikora/qgis-miniULDK/blob/b6b7542c117cc2507e086ecdb898b520a61bb186/assets/MiniULDK_1.gif)

### **2. Przycisk ustawień**
Otwiera okno ustawień, w którym można zdecydować, jak mają być obsługiwane pobrane działki.

### **Okno ustawień**
Okno ustawień zawiera trzy główne sekcje:

#### **SHP**
- włączenie zapisu pobieranych działek do SHP,
- wskazanie folderu docelowego,
- każda pobrana działka to osobny plik SHP, o nazwie **numer_obrebu.numer_dzialki** (np. **0003.204.shp**)
- opcję dodawania zapisanych warstw do projektu.

#### **GPKG**
- włączenie zapisu pobieranych działek do GeoPackage,
- wskazanie pliku GPKG,
- każda pobrana działka to osobna warstwa w pliku GPKG, o nazwie **numer_obrebu.numer_dzialki** (np. **0003.204**)
- opcję dodawania zapisanych warstw do projektu.

![MiniULDK_2](https://github.com/michal-k-sikora/qgis-miniULDK/blob/b6b7542c117cc2507e086ecdb898b520a61bb186/assets/MiniULDK_2.gif)

#### **Widok**
- opcję automatycznego przybliżania widoku do wskazanej działki.

Wtyczka pokazuje także bieżące komunikaty podczas pracy, np.:
- informację o poprawnym pobraniu działki,
- informację o braku działki pod wskazanym punktem,
- komunikaty o błędach lub nieprawidłowych ustawieniach.

![MiniULDK_3](https://github.com/michal-k-sikora/qgis-miniULDK/blob/b6b7542c117cc2507e086ecdb898b520a61bb186/assets/MiniULDK_3.png)

---

## Instalacja

### **1. Instalacja z ZIP**
1. Pobierz plik `.zip` z wtyczką.
2. W QGIS przejdź do:  
   **Wtyczki → Zarządzaj i instaluj wtyczki… → Zainstaluj z ZIP**
3. Wskaż pobrany plik `.zip`.
4. Po instalacji wtyczka pojawi się na pasku narzędzi **OnGeo**.

### **2. Instalacja ręczna**
Skopiuj folder wtyczki `miniuldk` do katalogu wtyczek QGIS dla używanego profilu.

Na przykład na Windows będzie to standardowy katalog profilu QGIS w folderze użytkownika.

---

## Wymagania

- **QGIS 3.28+**  
- W przyszłości wtyczka uzyska zgodność z **QGIS 4.x**
- dostęp do internetu podczas pobierania działek z usługi ULDK

W praktyce warto używać aktualnej wersji QGIS i aktualnej wersji wtyczki.

---

## Jak używać wtyczki

1. Uruchom QGIS i upewnij się, że wtyczka jest aktywna.
2. Na pasku **OnGeo** kliknij przycisk **MiniULDK**.
3. Kliknij w wybrane miejsce na mapie.
4. Jeśli w tym miejscu dostępna jest działka ewidencyjna, wtyczka pobierze ją i doda do warstwy wynikowej w projekcie.
5. Jeśli chcesz, wcześniej otwórz **Ustawienia MiniULDK** i włącz:
   - zapis do SHP,
   - zapis do GPKG,
   - dodawanie zapisanych warstw do projektu,
   - automatyczne przybliżanie widoku.
6. Aby przerwać działanie narzędzia, naciśnij **ESC**.

Dla poprawnego wskazywania działek warto pracować w projekcie z prawidłowo ustawionym układem współrzędnych.

---

## Przykłady zastosowań

- szybkie pobranie pojedynczej działki do bieżącego projektu,
- zebranie kilku wskazanych działek do dalszej analizy przestrzennej,
- utworzenie roboczej warstwy działek pobranych z różnych lokalizacji,
- zapis wybranych działek do osobnych plików,
- przygotowanie danych do dalszej pracy projektowej lub analitycznej.

---

## Autorzy

**Michał Sikora, Radosław Seweryn**  
Szkolenia i usługi GIS: **https://szkolenia.ongeo.pl/**  
Kontakt: **michal.sikora@ongeo.pl, radoslaw.seweryn@ongeo.pl**

---

# [EN] MiniULDK

**MiniULDK** is a QGIS plugin designed for **quick parcel retrieval directly from the map canvas**.  
It works from the **OnGeo** toolbar - you activate the tool, click on the map, and the plugin downloads the parcel geometry and adds it to the result layer in the current project.

The plugin is intended for simple, fast day-to-day work with individual cadastral parcels in QGIS.  
It can also save downloaded parcels to **SHP** or **GPKG** files and optionally zoom to the selected parcel automatically.

---

## Features

The plugin allows you to:

- download a cadastral parcel by clicking on the map,
- use the tool directly from the shared **OnGeo** toolbar,
- create a result layer with downloaded parcels in the current project,
- automatically fill in basic parcel attributes,
- save selected parcels to **SHP** files,
- save selected parcels to a **GPKG** file,
- optionally add saved layers to the project,
- optionally zoom to the clicked parcel,
- cancel the active tool with the **ESC** key,
- store selected settings within the QGIS project.

---

## Interface

The plugin provides two main interface elements:

### **1. MiniULDK button on the OnGeo toolbar**
This button activates the parcel selection tool.  
After enabling it, you can click directly on the map to download parcels.

### **2. Settings button**
This opens the settings dialog, where you can control how downloaded parcels should be handled.

### **Settings dialog**
The dialog contains three main sections:

#### **SHP**
- enable saving downloaded parcels to SHP,
- choose the target folder,
- optionally add saved parcels to the project.

#### **GPKG**
- enable saving downloaded parcels to GeoPackage,
- choose the target GPKG file,
- optionally add saved parcels to the project.

#### **View**
- enable automatic zoom to the selected parcel.

The plugin also displays status messages while you work, for example:
- successful parcel download,
- no parcel found at the clicked location,
- export or settings warnings,
- other runtime information.

---

## Installation

### **1. Install from ZIP**
1. Download the plugin `.zip` file.
2. In QGIS go to:  
   **Plugins → Manage and Install Plugins… → Install from ZIP**
3. Select the downloaded `.zip` file.
4. After installation, the plugin appears on the **OnGeo** toolbar.

### **2. Manual installation**
Copy the `miniuldk` plugin folder into the QGIS plugins directory for the selected user profile.

On Windows this is typically the standard QGIS profile plugins folder inside the user profile directory.

---

## Requirements

- **QGIS 3.x**
- compatibility with **QGIS 4.x** depends on the plugin version
- internet access while downloading parcels from the ULDK service

In practice, it is best to use a current QGIS version together with the latest plugin release.

---

## How to use the plugin

1. Start QGIS and make sure the plugin is enabled.
2. On the **OnGeo** toolbar, click **MiniULDK**.
3. Click on the map where you want to retrieve a parcel.
4. If a parcel is available at that location, the plugin downloads it and adds it to the result layer in the project.
5. If needed, open **MiniULDK Settings** first and enable:
   - SHP export,
   - GPKG export,
   - adding saved layers to the project,
   - automatic zoom.
6. To cancel the tool, press **ESC**.

For reliable parcel selection, it is recommended to work in a project with a correctly configured coordinate reference system.

---

## Practical use cases

- quickly downloading a single parcel into the current project,
- collecting multiple selected parcels for spatial analysis,
- building a temporary working layer of parcels from different locations,
- exporting selected parcels to files,
- preparing parcel data for further project or analysis work.

---

## Authors

**Michał Sikora, Radosław Seweryn**  
Szkolenia i usługi GIS: **https://szkolenia.ongeo.pl/**  
Kontakt: **michal.sikora@ongeo.pl, radoslaw.seweryn@ongeo.pl**

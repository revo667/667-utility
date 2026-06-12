import src.programs
import subprocess

ALL_PROGRAMS = {
    **src.programs.DEV_PROGRAMS,
    **src.programs.TOOLS,
    **src.programs.BASIC_APPS

}

def show_menu():
    print("\n=== YÜKLENEBİLİR PROGRAM LİSTESİ ===\n")
    for i, (name, winget_id) in enumerate(ALL_PROGRAMS.items(), 1):
        print(f"  [{i}] {name:<25} | {winget_id}")

    print("\n  [0] Çıkış")

def install_program(number):
    # Seçimi listeden al
    programs_list = list(ALL_PROGRAMS.items())

    if number == 0:
        print("Çıkılıyor...")
        return False

    elif 1 <= number <= len(programs_list):
        name, winget_id = programs_list[number - 1]
        print(f"\n📦 {name} yükleniyor...")
        print(f"   Komut: winget install --id {winget_id}")

        # GERÇEK YÜKLEME İÇİN:
        subprocess.run(["winget", "install", "--id", winget_id, "--accept-source-agreements"])
        print(f"✅ {name} başarıyla yüklendi!")

        return True
    
    else:
        print("Gecersiz secim")
        return True
    

running= True
while running:
    show_menu()


    try:
        
        secim = int(input("\nHangi programı yüklemek istiyorsun? (Seçim yap): "))

        running = install_program(secim)

    except ValueError:
        print("Lütfen sadece listedeki rakamlardan birini gir!"),

print(show_menu())
PROGRAM PLC_PRG
VAR
    // Mapeamento corrigido
    I00_Stop AT %IX0.0 : BOOL;  // NF
    I01_Start AT %IX0.1 : BOOL; // NA
    I02_Reset AT %IX0.2 : BOOL; // NA
    I03_Sensor AT %IX0.3 : BOOL; // NA
    
    Q00_Motor AT %QX0.0 : BOOL;
    Q01_Avanca AT %QX0.1 : BOOL;
    Q02_Recua AT %QX0.2 : BOOL;
    Q03_Lampada AT %QX0.3 : BOOL;

    Estado AT %MW0 : INT := 0;
    Contador_Pecas AT %MW1 : INT := 0;
    
    // Temporizadores
    TON_Espera : TON;
    TON_Avanco : TON;
    TON_Recuo : TON;
END_VAR

// Lógica de Segurança Global: Se Stop (NF) for pressionado, para tudo.
IF NOT I00_Stop THEN
    Estado := 0;
END_IF;

// Instância dos temporizadores
TON_Espera(IN := (Estado = 2), PT := T#1S);
TON_Avanco(IN := (Estado = 3), PT := T#3S);
TON_Recuo(IN := (Estado = 4), PT := T#2S);

CASE Estado OF
    0: // ESTADO DESLIGADO
        Q00_Motor := FALSE;
        Q01_Avanca := FALSE;
        Q02_Recua := TRUE; 
        Q03_Lampada := FALSE;
        
        IF I01_Start THEN
            Estado := 1;
        END_IF;

    1: // PROCESSO ATIVO
        Q00_Motor := TRUE;
        IF I03_Sensor THEN
            Estado := 2;
        END_IF;

    2: // SENSOR DETECTOU - AGUARDA 1s
        Q00_Motor := FALSE;
        IF TON_Espera.Q THEN
            Estado := 3;
        END_IF;

    3: // AVANÇA
        Q01_Avanca := TRUE;
        Q02_Recua := FALSE;
        IF TON_Avanco.Q THEN
            Estado := 4;
        END_IF;

    4: // RECUA
        Q01_Avanca := FALSE;
        Q02_Recua := TRUE;
        IF TON_Recuo.Q THEN
            Estado := 5;
        END_IF;

    5: // CONTAGEM E REINÍCIO
        Contador_Pecas := Contador_Pecas + 1;
        IF Contador_Pecas >= 5 THEN
            Estado := 6;
        ELSE
            Estado := 1;
        END_IF;

    6: // LOTE CONCLUÍDO
        Q00_Motor := FALSE;
        Q03_Lampada := TRUE;
        IF I02_Reset THEN
            Contador_Pecas := 0;
            Q03_Lampada := FALSE;
            Estado := 1;
        END_IF;
END_CASE;
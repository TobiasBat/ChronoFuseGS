#include "ScreenCapturer.h"

#include "SplattingActor.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Engine/Engine.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/GameViewportClient.h"
#include "HAL/IConsoleManager.h"

AScreenCapturer::AScreenCapturer()
{
    PrimaryActorTick.bCanEverTick = false;
    CaptureComponent = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("CaptureComponent"));
    RootComponent = CaptureComponent;

    CaptureComponent->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
    FallBackWidth  = 1920;
    FallBackHeight = 1080;
    StaticRT = nullptr;
    bRTInitialized = false;

    AllTime4Combinations = TArray<float>({
        0,0,0,0,
        
        1,0,0,0,
        0,1,0,0,
        0,0,1,0,
        0,0,0,1,
        
        1,1,0,0,
        1,0,1,0,
        1,0,0,1,
        0,1,1,0,
        0,1,0,1,
        0,0,1,1,
        
        0,1,1,1,
        1,0,1,1,
        1,1,0,1,
        1,1,1,0,

        1,1,1,1
    });

    AllTime3Combinations = TArray<float>({
        0,0,0,
        
        1,0,0,
        0,1,0,
        0,0,1,
        
        1,1,0,
        1,0,1,
        0,1,1,
        
        1,1,1
    });

    NumT = 4; 
}

void AScreenCapturer::BeginPlay()
{
    Super::BeginPlay();
    TryInitializeRT();
}

void AScreenCapturer::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);
    if (GEngine && GEngine->GameViewport && ViewportResizedHandle.IsValid())
    {
        GEngine->GameViewport->Viewport->ViewportResizedEvent.Remove(ViewportResizedHandle);
        ViewportResizedHandle.Reset();
    }
}

void AScreenCapturer::TryInitializeRT()
{
    if (bRTInitialized) return;
    if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport)
    {
        FIntPoint PhysSize = GEngine->GameViewport->Viewport->GetSizeXY();

        if (PhysSize.X > 0 && PhysSize.Y > 0)
        {
            FallBackWidth  = PhysSize.X;
            FallBackHeight = PhysSize.Y;
            UE_LOG(LogTemp, Log, TEXT("Capturer: physical size %dx%d"), FallBackWidth, FallBackHeight);

            InitRT();
            return;
        }
    }

    // Viewport not ready yet 
    if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport)
    {
        ViewportResizedHandle = GEngine->GameViewport->Viewport->ViewportResizedEvent.AddUObject(
            this, &AScreenCapturer::OnViewportResized);
    }
}

void AScreenCapturer::OnViewportResized(FViewport* Viewport, uint32)
{
    if (bRTInitialized) return;

    FIntPoint PhysSize = Viewport->GetSizeXY();
    if (PhysSize.X <= 0 || PhysSize.Y <= 0) return;

    FallBackWidth  = PhysSize.X;
    FallBackHeight = PhysSize.Y;
    UE_LOG(LogTemp, Log, TEXT("Capturer: deferred init — physical size %dx%d"), FallBackWidth, FallBackHeight);

    InitRT();

    // Unbind — we only need this once
    Viewport->ViewportResizedEvent.Remove(ViewportResizedHandle);
    ViewportResizedHandle.Reset();
}

void AScreenCapturer::InitRT()
{
    if (FallBackWidth <= 0 || FallBackHeight <= 0)
    {
        FallBackWidth  = 1920;
        FallBackHeight = 1080;
        UE_LOG(LogTemp, Warning, TEXT("Capturer: invalid size, falling back to 1920x1080"));
    }

    float ScreenPct = 100.f;
    if (auto* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage")))
        ScreenPct = CVar->GetFloat();

    int32 RTWidth  = FMath::Max(1, FMath::RoundToInt(FallBackWidth  * ScreenPct / 100.f));
    int32 RTHeight = FMath::Max(1, FMath::RoundToInt(FallBackHeight * ScreenPct / 100.f));

    if (!StaticRT)
    {
        StaticRT = NewObject<UTextureRenderTarget2D>(this);
        StaticRT->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA8;
        StaticRT->InitAutoFormat(RTWidth, RTHeight);
        StaticRT->TargetGamma = 2.2f;
        StaticRT->UpdateResource();
        CaptureComponent->TextureTarget = StaticRT;
    }
    else
    {
        StaticRT->ResizeTarget(RTWidth, RTHeight);
        StaticRT->UpdateResource();
    }

    SyncShowFlagsFromViewport();
    bRTInitialized = true;
    UE_LOG(LogTemp, Log, TEXT("Capturer: RT initialized at %dx%d (ScreenPct=%.0f)"), RTWidth, RTHeight, ScreenPct);
}

void AScreenCapturer::SyncShowFlagsFromViewport() const
{
    if (!GEngine || !GEngine->GameViewport) return;
    FEngineShowFlags* ViewportFlags = GEngine->GameViewport->GetEngineShowFlags();
    if (!ViewportFlags) return;

    CaptureComponent->ShowFlags = *ViewportFlags;
    CaptureComponent->ShowFlags.SetTemporalAA(false);
    CaptureComponent->ShowFlags.SetMotionBlur(false);
}

void AScreenCapturer::TakeScreenshot(FString FileName)
{
    // If the deferred init hasn't fired yet, try once more before capturing
    if (!bRTInitialized)
    {
        TryInitializeRT();
        if (!bRTInitialized)
        {
            UE_LOG(LogTemp, Error, TEXT("Capturer: RT not initialized, cannot capture!"));
            return;
        }
    }

    APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
    if (PC && PC->PlayerCameraManager)
    {
        SetActorLocationAndRotation(
            PC->PlayerCameraManager->GetCameraLocation(),
            PC->PlayerCameraManager->GetCameraRotation());
        CaptureComponent->FOVAngle      = PC->PlayerCameraManager->GetFOVAngle();
        CaptureComponent->PostProcessSettings =
            PC->PlayerCameraManager->GetCameraCacheView().PostProcessSettings;
    }

    SyncShowFlagsFromViewport();
    RescaleRTToCurrentScreenPercentage();

    PendingFileName = FileName;
    if (!PendingFileName.EndsWith(".png")) PendingFileName += ".png";

    if (!StaticRT || !CaptureComponent) return;

    StaticRT->UpdateResource();
    CaptureComponent->CaptureSource      = ESceneCaptureSource::SCS_FinalColorLDR;
    CaptureComponent->bCaptureEveryFrame = false;
    CaptureComponent->CaptureScene();
    FlushRenderingCommands();

    UKismetRenderingLibrary::ExportRenderTarget(GetWorld(), StaticRT, SavePath.Path, PendingFileName);
    UE_LOG(LogTemp, Log, TEXT("Capturer: saved %s/%s"), *SavePath.Path, *PendingFileName);
}

void AScreenCapturer::RescaleRTToCurrentScreenPercentage() const
{
    float ScreenPct = 100.f;
    static IConsoleVariable* CVar =
        IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"));
    if (CVar) ScreenPct = CVar->GetFloat();

    int32 W = FMath::Max(1, FMath::RoundToInt(FallBackWidth  * ScreenPct / 100.f));
    int32 H = FMath::Max(1, FMath::RoundToInt(FallBackHeight * ScreenPct / 100.f));

    if (StaticRT && (StaticRT->SizeX != W || StaticRT->SizeY != H))
    {
        StaticRT->ResizeTarget(W, H);
        StaticRT->UpdateResource();
    }
}

void AScreenCapturer::CaptureAllTimeCombinations()
{
    UE_LOG(LogTemp, Log, TEXT("Capturing all time Combinations..."));
    AllTmeCapturingIndex = 0;
    CaptureAllTimeRec();   
}

void AScreenCapturer::CaptureAllTimeRec()
{
    ASplattingActor* SplattingActor = Cast<ASplattingActor>(UGameplayStatics::GetActorOfClass(GetWorld(), ASplattingActor::StaticClass()));

    if (SplattingActor && AllTmeCapturingIndex < (SplattingActor->NumberOfTimes() * SplattingActor->NumberOfTimes()))
    {
        UE_LOG(LogTemp, Log, TEXT("Capturing Index: %i"), AllTmeCapturingIndex);
        
        FString FullPath = FString::Printf(TEXT("test%i.png"), AllTmeCapturingIndex);
        UE_LOG(LogTemp, Log, TEXT("%s"), *FullPath);

        TArray<float> TimeSelection = TArray<float>();
        TimeSelection.Init(0,4);
        TimeSelection[0] = AllTime4Combinations[AllTmeCapturingIndex * 4 + 0];
        TimeSelection[1] = AllTime4Combinations[AllTmeCapturingIndex * 4 + 1];
        TimeSelection[2] = AllTime4Combinations[AllTmeCapturingIndex * 4 + 2];
        TimeSelection[3] = AllTime4Combinations[AllTmeCapturingIndex * 4 + 3];
        
        SplattingActor->SetActivationSelection(TimeSelection);
        TakeScreenshot(FullPath); 
        AllTmeCapturingIndex++;

        GetWorld()->GetTimerManager().SetTimer(TimerHandle_AllTimeCapture, this, &AScreenCapturer::CaptureAllTimeRec, 1.0f, false);
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("Capture Sequence Complete or SplattingActor Missing!"));
    }
}

TArray<float> AScreenCapturer::GetTimeCombination(int Index)
{
    TArray<float> TimeSelection = TArray<float>();
    if (NumT == 3)
    {
        TimeSelection.Init(0,3);
        if (Index * 3 + 2 < AllTime3Combinations.Num())
        {
            TimeSelection[0] = AllTime3Combinations[Index * 3 + 0];
            TimeSelection[1] = AllTime3Combinations[Index * 3 + 1];
            TimeSelection[2] = AllTime3Combinations[Index * 3 + 2];
        }
    } else
    {
        TimeSelection.Init(0,4);
        if (Index * 4 + 3 < AllTime4Combinations.Num())
        {
            TimeSelection[0] = AllTime4Combinations[Index * 4 + 0];
            TimeSelection[1] = AllTime4Combinations[Index * 4 + 1];
            TimeSelection[2] = AllTime4Combinations[Index * 4 + 2];
            TimeSelection[3] = AllTime4Combinations[Index * 4 + 3];
        }
    }
    return TimeSelection;    
}

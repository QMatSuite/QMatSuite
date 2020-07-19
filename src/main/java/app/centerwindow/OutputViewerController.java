/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerwindow;

import java.awt.Desktop;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.LineNumberReader;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.ResourceBundle;
import java.util.Scanner;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart.Data;
import javafx.scene.chart.XYChart.Series;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.ListCell;
import javafx.scene.control.ListView;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.ScrollPane.ScrollBarPolicy;
import javafx.scene.control.ToggleButton;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.text.Text;
import javafx.scene.text.TextFlow;
import javafx.util.Callback;
import main.MainClass;
import com.consts.Constants.EnumAnalysis;
import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumFileCategory;
import com.consts.Constants.EnumNameList;
import com.consts.Constants.EnumStep;
import com.programconst.DefaultFileNames;
import com.programconst.ProgrammingConsts;
import app.input.InputGeoController;

public class OutputViewerController implements Initializable{

    @FXML private HBox rootHbox;

    @FXML private VBox vboxFiles,
    vboxMainPlot;

    @FXML private ListView<String> listFiles;
    
    @FXML private ScrollPane displayScroll;
    
    @FXML private Button deleteFileButton,
    openAsButton,
    buttonRefreshFiles,
    buttonRefresh,
    buttonSaveGeo,
	buttonShowInSystem;
    
    @FXML private Label labelFileCategory,
    labelPlot,
    labelK;
    
    @FXML private ComboBox<EnumAnalysis> comboAnalysis;
    
    @FXML private ComboBox<String> comboPlot,
    comboHighSymK;
    
    @FXML private HBox hboxPlotToolbar,
    hboxBandsToolbar;
    
    @FXML private ToggleButton buttonShowMarker;
    
    private TextFlow textFlowDisplay;
    
    private MainClass mainClass;
    
    private File calcFolder;
    
    private File inoutFiles;
    
    private EnumFileCategory fileCategory;
    
    private FileDataClass fileData;
    
    private NumberAxis xAxis;

    private NumberAxis yAxis;

    private LineChart<Double, Double> lineChart;
    
    private final ArrayList<String> plotTypeDos;
    
    private ArrayList<String> plotTypeStdOut;
    
    private InputGeoController contGeo;
    
    private WorkScene3D geometry3d;
    
    private double minY,
	maxY,
	minX,
	maxX;
    		
    public OutputViewerController(MainClass mc, InputGeoController cg) {
    	mainClass = mc;
    	contGeo = cg;
    	textFlowDisplay = new TextFlow();
    	fileData = new FileDataClass();
    	xAxis = new NumberAxis();xAxis.setAutoRanging(true);xAxis.setForceZeroInRange(false);
    	yAxis = new NumberAxis();yAxis.setAutoRanging(true);yAxis.setForceZeroInRange(false);
    	
    	geometry3d = new WorkScene3D();
    	geometry3d.addAnimate3D(fileData);//add animation panel and link the data file
    	geometry3d.buildGeometry(fileData.getGeoAgent());//link the geoAgent in fileData to the workscene3d plot
    	
    	
    	lineChart = new LineChart(xAxis, yAxis);
    	
    	plotTypeDos = new ArrayList<String>() {
    		{
	    		add("DOS"); //0
	    		add("Integrated DOS"); //1 
    		}
		};
		plotTypeStdOut= new ArrayList<String>();
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		geometry3d.centerSubScene(displayScroll);
		
		lineChart.prefWidthProperty().bind(displayScroll.widthProperty());
		lineChart.setCreateSymbols(false);
		//lineChart.prefHeightProperty().bind(workSpaceTabPane.heightProperty());
		
		comboHighSymK.getSelectionModel().selectedIndexProperty().addListener((ov, oldTab, newTab) -> {
			if(fileData==null || !EnumFileCategory.bandsDatGnu.equals(fileCategory)) {return;}
			if(fileData.getBandsHighSymmetryK().isEmpty()) {return;}
			int selectInd = (int)newTab;
			if(selectInd<0 || selectInd>=fileData.getBandsHighSymmetryK().size()) {return;} 
			labelK.setText("k="+fileData.getBandsHighSymmetryK().get(selectInd)
					+",x="+fileData.getBandsHighSymmetryKXCoor().get(selectInd));
			//textLabelK.setText(kpointName.get(selectInd));
		});
//		buttonSetLabelK.setOnAction((event) -> {
//			if(fileData==null || !EnumFileCategory.bandsDatGnu.equals(fileCategory)) {return;}
//			int selectInd = comboHighSymK.getSelectionModel().getSelectedIndex();
//			if(selectInd<0 || selectInd>=kpointName.size()) {return;} 
//			kpointName.set(selectInd, textLabelK.getText());
//			this.plot2dBands();
//		});
		//comboPlot.setVisible(false);labelPlot.setVisible(false);
		hboxPlotToolbar.setVisible(false);
		hboxBandsToolbar.setVisible(false);
		listFiles.setCellFactory(new Callback<ListView<String>, ListCell<String>>() {
	        @Override 
	        public ListCell<String> call(ListView<String> param) {
	            return new ListCell<String>() {
	                @Override 
	                protected void updateItem(String item, boolean empty) {
	                    super.updateItem(item, empty);
	                    if (item==null) {
	                    	setStyle("-fx-font-weight: normal; "
	                    			+"-fx-border-color: white; ");
	                    	setText(item);
	                    }
	                    else {
	                    	if (isFileImportant(item)) {
	                        	setStyle("-fx-font-weight: bolder; "
	                        			+"-fx-border-color: green; ");
	                        } else {
	                        	setStyle("-fx-font-weight: normal; "
	                        			+"-fx-border-color: white; ");
	                        }
		                    setText(item);
	                    }
	                }

	            };
	        }
		});
		listFiles.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "listFiles: "+oldTab + "," + newTab);
			
			fileCategory = null;
			fileData.clearAll();buttonSaveGeo.setDisable(true);
			labelFileCategory.setText("");
//			EnumAnalysis analTmp = comboAnalysis.getSelectionModel().getSelectedItem();//cache the selected item before clearing
			comboAnalysis.getItems().clear();
			
			if(newTab==null || newTab.isEmpty()) return;
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			inoutFiles = new File(calcFolder,newTab);
			if(!inoutFiles.canRead()) return;
			
			if(newTab.endsWith(ProgrammingConsts.stdinExtension)) {fileCategory = EnumFileCategory.stdin;}
			else if(newTab.endsWith(ProgrammingConsts.stdoutExtension)) {fileCategory = EnumFileCategory.stdout;}
			else if(newTab.endsWith(ProgrammingConsts.stderrExtension)) {fileCategory = EnumFileCategory.stderr;}
			else if(newTab.endsWith(ProgrammingConsts.dosExtension)) {fileCategory = EnumFileCategory.dos;}
			else if(newTab.contains(DefaultFileNames.bandsDatGnu)) {fileCategory = EnumFileCategory.bandsDatGnu;}
			else if(newTab.contains(DefaultFileNames.tddftPlotSDat)){fileCategory = EnumFileCategory.tddftPlotSDat;}
			else if(newTab.contains(DefaultFileNames.calcSaveFile)||newTab.contains(DefaultFileNames.projSaveFile)) 
			{fileCategory = EnumFileCategory.save;}
			else if(newTab.contains(".xml")) {fileCategory = EnumFileCategory.xmlout;}
			else if(newTab.toLowerCase().contains("crash")) {fileCategory = EnumFileCategory.crash;}
			else if(inoutFiles.isDirectory()) {fileCategory = EnumFileCategory.directory;}
			else {fileCategory = EnumFileCategory.unknown;}
			
			fileData.fileCategory = fileCategory;
			
			if(fileCategory!=null) {labelFileCategory.setText(fileCategory.toString());}//should not be null until this point!
			
			loadFile();
			
			if(fileCategory!=null) {
				comboAnalysis.getItems().addAll(EnumAnalysis.text);//always has the option of show in text
				if(EnumFileCategory.stdout.equals(fileCategory) || EnumFileCategory.dos.equals(fileCategory) 
						|| EnumFileCategory.bandsDatGnu.equals(fileCategory) || EnumFileCategory.tddftPlotSDat.equals(fileCategory)) {
					comboAnalysis.getItems().addAll(EnumAnalysis.info);
					comboAnalysis.getItems().addAll(EnumAnalysis.plot2D);
				}
				if(fileData.isMD || fileData.isOpt) {comboAnalysis.getItems().addAll(EnumAnalysis.plot3D);}
				
//				if(analTmp!=null && comboAnalysis.getItems().contains(analTmp)) {
//					//select back the choice before
//					comboAnalysis.getSelectionModel().select(analTmp);
//				}
//				else {
//					//select text first if there has been no selection
//					if(comboAnalysis.getItems().contains(EnumAnalysis.plot2D)) {
//						comboAnalysis.getSelectionModel().select(EnumAnalysis.plot2D);
//					}
//					else {
//						comboAnalysis.getSelectionModel().select(EnumAnalysis.text);
//					}
//				}
				if(comboAnalysis.getItems().contains(EnumAnalysis.plot2D)) {
					if(EnumFileCategory.stdout.equals(fileCategory) && !this.fileData.isMD  && !this.fileData.isOpt  
							&& !this.fileData.hasScf) {
						comboAnalysis.getSelectionModel().select(EnumAnalysis.info);
					}
					else {
						comboAnalysis.getSelectionModel().select(EnumAnalysis.plot2D);
					}
				}
				else {
					comboAnalysis.getSelectionModel().select(EnumAnalysis.text);
				}
			}
			
			updateIoDisplay();//*** not efficient because runs twice
		});
		
		buttonRefresh.setOnAction((event) -> {
			if((fileData.isMD || fileData.isOpt) && !comboAnalysis.getItems().contains(EnumAnalysis.plot3D)) {comboAnalysis.getItems().addAll(EnumAnalysis.plot3D);}
			loadFile();
			updateIoDisplay();
		});
		comboAnalysis.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab!=null) {updateIoDisplay();}
		});
		comboPlot.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab!=null) {updateIoDisplay();}//very crucial to check null here!
		});
		openAsButton.setOnAction((event) -> {
			if(inoutFiles==null || !inoutFiles.canRead()) return;
			if( Desktop.isDesktopSupported() )
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(inoutFiles);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
		});
		buttonShowInSystem.setOnAction((event) -> {
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			if( Desktop.isDesktopSupported() )
			{
			    new Thread(() -> {
				   try {
				       Desktop.getDesktop().open(calcFolder);
				   } catch (IOException e1) {
				       e1.printStackTrace();
				   }
			       }).start();
			}
		});
		buttonSaveGeo.setDisable(true);
		buttonSaveGeo.setOnAction((event) -> {
			if(fileData==null) {return;}
//			ArrayList<Atom> atomList = fileData.getFinalAtomicPositions();
//			CellParameter cellPara = fileData.getFinalCellParameter();
//			Double alat = fileData.getAlat();
//			if(atomList==null || atomList.isEmpty() || alat==null ) {return;}
//			String calcFolderName = listCalcFolders.getSelectionModel().getSelectedItem();
			String calcFolderName = mainClass.projectManager.getCurrentCalcName();
			if(calcFolderName==null) {return;}
			//mainClass.projectManager.addGeoList(calcFolderName, atomList, cellPara, alat);
			mainClass.projectManager.addGeoList(calcFolderName, fileData.getGeoAgent());
			if(contGeo!=null) {contGeo.loadProjectParameters();}
		});
		
		buttonShowMarker.selectedProperty().addListener((observable, oldValue, newValue) ->{
			if(newValue==null) return;
			lineChart.setCreateSymbols(newValue);
		});
		buttonShowMarker.setSelected(true);
		
//		buttonRefreshFolder.setOnAction((event) -> {
//			int tmpInt = listCalcFolders.getSelectionModel().getSelectedIndex();
//			updateProjectFolder();
//			if(tmpInt>=0 && listCalcFolders.getItems()!=null && listCalcFolders.getItems().size()>tmpInt) {
//				listCalcFolders.getSelectionModel().select(tmpInt);
//			}
//		});
		buttonRefreshFiles.setOnAction((event) -> {
			updateFilesInCalcFolder(false);
		});
//		deleteFolderButton.setOnAction((event) -> {
//			try {
//				deleteDirectory(calcFolder);
//			} catch (IOException e) {
//				e.printStackTrace();
//			}
//			updateProjectFolder();
//		});
		deleteFileButton.setOnAction((event) -> {
			try {
				deleteDirectory(inoutFiles);
			} catch (IOException e) {
				e.printStackTrace();
			}
			updateFilesInCalcFolder(true);
		});
		
	}
	private boolean isFileImportant(String item) {
		boolean isScf = (calcFolder!=null && 
        		calcFolder.getName().toLowerCase().contains("scf")
        		&& !calcFolder.getName().toLowerCase().contains("nscf")
        		&& item.contains(EnumStep.SCF.toString())
        		&& item.endsWith(ProgrammingConsts.stdoutExtension));
        boolean isOpt = (calcFolder!=null
        		&& item.contains(EnumStep.OPT.toString())
        		&& item.endsWith(ProgrammingConsts.stdoutExtension));
        boolean isMd = (calcFolder!=null
        		&& item.contains(EnumStep.BOMD.toString())
        		&& item.endsWith(ProgrammingConsts.stdoutExtension));
        return (item.endsWith(ProgrammingConsts.dosExtension)
        		|| item.contains(DefaultFileNames.bandsDatGnu)
        		|| item.contains(DefaultFileNames.tddftPlotSDat)
        		|| isScf || isOpt || isMd);
	}
	public void calculationFolderChange(String newCalcFolderName) {
		fileData.clearAll();buttonSaveGeo.setDisable(true);
		
		if(newCalcFolderName==null || newCalcFolderName.isEmpty()) return;
		
		File pjFolder = getProjectFolder();
		if(pjFolder==null || !pjFolder.canRead()) {
			listFiles.getItems().clear();
			//return;//comment out so that calcFolder is always updated
		}
		if(pjFolder==null) {return;}
		calcFolder = new File(pjFolder,newCalcFolderName);
		
		updateFilesInCalcFolder(true);
	}
	private boolean deleteDirectory(File directoryToBeDeleted) throws IOException {
	    File[] contentFiles = directoryToBeDeleted.listFiles();
	    if (contentFiles != null) {
	        for (File file : contentFiles) {
	            deleteDirectory(file);
	        }
	    }
	    return directoryToBeDeleted.delete();
	}
	private void updateFilesInCalcFolder(boolean forceClean) {
		
		int tmpInt = listFiles.getSelectionModel().getSelectedIndex();
		
		if(forceClean) {
			listFiles.getItems().clear();
		}

		if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
		
		ObservableList<String> listFilesItems = FXCollections.observableArrayList();
		
		File[] fileList = calcFolder.listFiles();
		for (File f : fileList) {
			listFilesItems.add(f.getName());
		}
		
		if(this.checkIdentity(listFilesItems, listFiles.getItems())) {
			return;//no change, do nothing
		}
		
		listFiles.getItems().clear();
		listFiles.getItems().addAll(listFilesItems);
		
		String itemImportant = null;
		for(String item:listFilesItems) {
			if(isFileImportant(item)) {
				itemImportant = item;//only take the first important one
				break;
			}
		}
		if(itemImportant!=null) {
			listFiles.getSelectionModel().select(itemImportant);//automatically select the "important/highlighted" output file
			//will invoke selection change listener and update "inoutFiles"
		}
		else if(tmpInt>=0 && listFiles.getItems().size()>tmpInt) {//if no important file, just keep selected index
			listFiles.getSelectionModel().select(tmpInt);
		}
		else if(!listFiles.getItems().isEmpty()){//select first file if nothing works
			listFiles.getSelectionModel().select(0);
		}
	}
	private void updateIoDisplay() {
		hboxBandsToolbar.setVisible(false);
		EnumAnalysis analTmp = comboAnalysis.getSelectionModel().getSelectedItem();
		
		displayScroll.setContent(null);
		displayScroll.setHbarPolicy(ScrollBarPolicy.AS_NEEDED);//reset scrolling capability
		displayScroll.setVbarPolicy(ScrollBarPolicy.AS_NEEDED);
		
		if(fileCategory==null || analTmp==null) return;
		
		boolean boolPlot = analTmp.equals(EnumAnalysis.plot2D);
		//comboPlot.setVisible(boolPlot);labelPlot.setVisible(boolPlot);
		hboxPlotToolbar.setVisible(boolPlot);
		
		if(analTmp.equals(EnumAnalysis.text)) {//show raw text
			displayScroll.setContent(textFlowDisplay);
			readTextFileToTextFlow();//only highlight input files
		}
		else {//show analysis
			displayScroll.setContent(textFlowDisplay);
			textFlowDisplay.getChildren().clear();
			if(fileCategory.equals(EnumFileCategory.stdout)) {
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dStdOut();}
				else if(analTmp.equals(EnumAnalysis.plot3D)) {plot3dStdOut();}
			}
			else if(fileCategory.equals(EnumFileCategory.dos)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dDos();}
				else if(analTmp.equals(EnumAnalysis.plot3D)) {textFlowDisplay.getChildren().add(new Text("No 3D view of this file type."));}
			}
			else if(fileCategory.equals(EnumFileCategory.tddftPlotSDat)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dTddft();}
				else if(analTmp.equals(EnumAnalysis.plot3D)) {textFlowDisplay.getChildren().add(new Text("No 3D view of this file type."));}
			}
			else if(fileCategory.equals(EnumFileCategory.bandsDatGnu)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dBands();}
				else if(analTmp.equals(EnumAnalysis.plot3D)) {textFlowDisplay.getChildren().add(new Text("No 3D view of this file type."));}
			}
			else {
				textFlowDisplay.getChildren().add(new Text("Analysis is not available for this file type."));
			}
		}
	}
	private boolean isSameTypeStdout(ArrayList<String> strTest) {
		ObservableList<String> comboTmp = comboPlot.getItems();
		if(comboTmp.size()!=strTest.size()) {return false;}
		for(int i=0;i<comboTmp.size();i++) {
			if(comboTmp.get(i)==null || !comboTmp.get(i).equals(strTest.get(i))) {return false;}
		}
		return true;
	}
	private void plot2dBands() {
		//high symmetry k points
		hboxBandsToolbar.setVisible(true);
	
		buttonShowMarker.setSelected(false);
		lineChart.getData().clear();
		
		Double fermiDos = fileData.fermiDos;
		ArrayList<ArrayList<ArrayList<Double>>> bandsDatArray = fileData.getBandsDatArray();
		
		if(bandsDatArray.isEmpty() || bandsDatArray.get(0).isEmpty()) {return;}
		
		xAxis.setLabel("k");
		yAxis.setLabel("E");
		
		minY = 1000.0;
		maxY = -1000.0;
		minX = 1000.0;
		maxX = -1000.0;
		
		//k,j,i
		//bands,k points,spins (1 or 2)
		for(int k=0;k<bandsDatArray.size();k++) {//different bands
			if(bandsDatArray.get(k).isEmpty()) {continue;}
			
			for(int i=1;i<bandsDatArray.get(k).get(0).size();i++) {//different columns (spins). Starting from 1 because 0 is xaxis
				
				Series<Double,Double> dataSeries1 = new Series<Double, Double>();
				lineChart.getData().add(dataSeries1);
				
				dataSeries1.setName("Band "+Integer.toString(k+1));
	
				for(int j=0;j<bandsDatArray.get(k).size();j++) {//different k points
					
					if(bandsDatArray.get(k).get(j).size() <= i) {break;}//a certain row does not have enough numbers
					Data<Double, Double> dt = new Data<Double, Double>(bandsDatArray.get(k).get(j).get(0), bandsDatArray.get(k).get(j).get(i));
					dataSeries1.getData().add(dt);
					//dt.getNode().setStyle("-fx-background-color: #4a86e8;");
					
					if(bandsDatArray.get(k).get(j).get(i)>maxY) {maxY=bandsDatArray.get(k).get(j).get(i);}
					if(bandsDatArray.get(k).get(j).get(i)<minY) {minY=bandsDatArray.get(k).get(j).get(i);}
					if(bandsDatArray.get(k).get(j).get(0)>maxX) {maxX=bandsDatArray.get(k).get(j).get(0);}
					if(bandsDatArray.get(k).get(j).get(0)<minX) {minX=bandsDatArray.get(k).get(j).get(0);}
				}
				
				//dataSeries1.getNode().setStyle("-fx-stroke: #4a86e8;");
				
				lineChart.getStyleClass().add("chart-series-line");
	        }
		}
		
		//Fermi energy
		if(fermiDos!=null) {
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			dataSeries1.getData().add(new Data<Double, Double>(minX, fermiDos));
			dataSeries1.getData().add(new Data<Double, Double>(maxX, fermiDos));
			dataSeries1.setName("Fermi Energy");
			
			lineChart.getData().add(dataSeries1);
			
			//-fx-stroke: #666666; 
			dataSeries1.getNode().setStyle("-fx-stroke-dash-array: 2 10 10 2; ");
		}
		
		//high symmetry k points
		if(fileData.getBandsHighSymmetryK().size()!=fileData.getBandsHighSymmetryKXCoor().size()) {
			return;}

		for(int i=0;i<fileData.getBandsHighSymmetryK().size();i++) {
			double dbTmp = fileData.getBandsHighSymmetryKXCoor().get(i);
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			lineChart.getData().add(dataSeries1);
			
			dataSeries1.getData().add(new Data<Double, Double>(dbTmp, minY));
			dataSeries1.getData().add(new Data<Double, Double>(dbTmp, maxY));
			//String strTmpName = kpointName.get(i).isEmpty()? "": "("+kpointName.get(i)+") ";
			dataSeries1.setName("k"+Integer.toString(i+1)+"="+
			fileData.getBandsHighSymmetryK().get(i)+",x="+fileData.getBandsHighSymmetryKXCoor().get(i));
		}
//		Text txt = new Text("sdsdsd");
//		displayScroll.setContent(new Group(lineChart,txt));
//		Point2D pd = lineChart.localToParent(minX, maxY);
//		//ShowAlert.showAlert(AlertType.INFORMATION, "Warning", ""+pd.getX()+","+ pd.getY());
//		txt.relocate(pd.getX(), 100.0);
        displayScroll.setContent(lineChart);
	}
	private void plot2dTddft() {
		buttonShowMarker.setSelected(false);
		
		lineChart.getData().clear();
		
		
		ArrayList<ArrayList<Double>> tddftArray = fileData.getTddftArray();
		ArrayList<String> tddftHeader = fileData.getTddftHeader();
		
		if(tddftArray.isEmpty()) {return;}
		
		xAxis.setLabel(tddftHeader.size()>0 ? tddftHeader.get(0):"Unknown (1st column)");
		yAxis.setLabel(tddftHeader.size()>1 ? tddftHeader.get(1):"Unknown (2nd column)");
		
		
		for(int i=1;i<tddftArray.get(0).size();i++) {//different columns (y axis). Starting from 1 because 0 is xaxis
			
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			String headerTmp = (tddftHeader.size()>i ? tddftHeader.get(i):"Unknown ("+Integer.toString(i)+"th column)");
			dataSeries1.setName(headerTmp);
			for(int j=0;j<tddftArray.size();j++) {
				if(tddftArray.get(j).size()<=i) {break;}//a certain row does not have enough numbers
				dataSeries1.getData().add(new Data<Double, Double>(tddftArray.get(j).get(0), 
						tddftArray.get(j).get(i)));
			}
			lineChart.getData().add(dataSeries1);
        }
		
        displayScroll.setContent(lineChart);
	}
	private void plot2dDos() {
		buttonShowMarker.setSelected(false);
		if(!isSameTypeStdout(plotTypeDos)) {
			comboPlot.getItems().clear();
			comboPlot.getItems().addAll(plotTypeDos);
			//ShowAlert.showAlert(AlertType.INFORMATION, "Info", "plot2dDos. Construct comboPlot.");
			comboPlot.getSelectionModel().select(0);
		}
		
		lineChart.getData().clear();
		
		String strSelect = comboPlot.getSelectionModel().getSelectedItem();
		boolean boolInteg;
		if(plotTypeDos.get(0).equals(strSelect)) {
			//add("DOS"); //0
			boolInteg = false;
		}
		else if(plotTypeDos.get(1).equals(strSelect)){
			//add("Integrated DOS"); //1 
			boolInteg = true;
		}
		else {
			lineChart.setTitle("Please select plotting type!");
			return;
		}
		
		Double fermiDos = fileData.fermiDos;
		ArrayList<ArrayList<Double>> dosArray = fileData.getDosArray();
		ArrayList<String> dosHeader = fileData.getDosHeader();
		
		if(dosArray.isEmpty()) {return;}
		
		xAxis.setLabel(dosHeader.size()>0 ? dosHeader.get(0):"Unknown (1st column)");
		yAxis.setLabel(strSelect);
		
		minY = 1000.0;
		maxY = -1000.0;
		
		for(int i=1;i<dosArray.get(0).size();i++) {//different columns (y axis). Starting from 1 because 0 is xaxis
			
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			String headerTmp = (dosHeader.size()>i ? dosHeader.get(i):"Unknown ("+Integer.toString(i)+"th column)");
			dataSeries1.setName(headerTmp);
			if(boolInteg != headerTmp.toLowerCase().contains("int") ) {continue;}
			for(int j=0;j<dosArray.size();j++) {
				if(dosArray.get(j).size()<=i) {break;}//a certain row does not have enough numbers
				dataSeries1.getData().add(new Data<Double, Double>(dosArray.get(j).get(0), dosArray.get(j).get(i)));
				if(dosArray.get(j).get(i)>maxY) {maxY=dosArray.get(j).get(i);}
				if(dosArray.get(j).get(i)<minY) {minY=dosArray.get(j).get(i);}
			}
			lineChart.getData().add(dataSeries1);
        }
		
		//Fermi energy
		if(fermiDos!=null) {
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			dataSeries1.getData().add(new Data<Double, Double>(fermiDos, minY));
			dataSeries1.getData().add(new Data<Double, Double>(fermiDos, maxY));
			dataSeries1.setName("Fermi Energy");
			lineChart.getData().add(dataSeries1);
		}
		
        displayScroll.setContent(lineChart);
        

	}
	private void plot3dStdOut() {
		//construct new plot type list
		plotTypeStdOut.clear();
		if(fileData.isMD || fileData.isOpt) {plotTypeStdOut.add("Geometry");}
		//plotTypeStdOut.add("With Force");
		//if(fileData.isMD) {plotTypeStdOut.add("With Velocity");}
		if(!isSameTypeStdout(plotTypeStdOut)) {
			comboPlot.getItems().clear();
			if(!plotTypeStdOut.isEmpty()) {
				comboPlot.getItems().addAll(plotTypeStdOut);
				comboPlot.getSelectionModel().select(0);//****run twice
			}
		}
		
		if(plotTypeStdOut.isEmpty()) {
			textFlowDisplay.getChildren().add(new Text("No available plot for this file type. SHOULD NOT REACH HERE!"));
			return;
		}
		
		String plotType = comboPlot.getSelectionModel().getSelectedItem();
		
		if(plotType==null) return;
		
		if(plotType.equals("Geometry")) {
			//ShowAlert.showAlert(AlertType.INFORMATION, "Info", "Plot Geometry");
			geometry3d.buildGeometry();
			geometry3d.updateAnimate3D();//update animate3D control panel
			AnchorPane acp = geometry3d.getRootPane();
			displayScroll.setContent(acp);

			//disable scrolling capability of the scrollpane so that it does not interfere with zoom-in/out of the workscene3d
			displayScroll.setHbarPolicy(ScrollBarPolicy.NEVER);
			displayScroll.setVbarPolicy(ScrollBarPolicy.NEVER);
		}
	}
	private void plot2dStdOut() {
		buttonShowMarker.setSelected(true);
		//construct new plot type list
		plotTypeStdOut.clear();
		if(fileData.isOpt) {
			plotTypeStdOut.add("OPT E conv");//if change here, remember to change later in this function
			plotTypeStdOut.add("OPT F conv");
			plotTypeStdOut.add("OPT P conv");
		}
		if(fileData.isMD) {
			plotTypeStdOut.add("Ekin");//if change here, remember to change later in this function
			plotTypeStdOut.add("Temperature");
			plotTypeStdOut.add("Ekin + Etot");
		}
		if(fileData.hasScf) {plotTypeStdOut.add("SCF E conv");}
		//check whether it is the same as in the combo. If yes, no update of the combo
		if(!isSameTypeStdout(plotTypeStdOut)) {
			comboPlot.getItems().clear();
			if(!plotTypeStdOut.isEmpty()) {
				comboPlot.getItems().addAll(plotTypeStdOut);
				//ShowAlert.showAlert(AlertType.INFORMATION, "Info", "plot2dStdOut. Construct comboPlot.");
				comboPlot.getSelectionModel().select(0);//****run twice
			}
		}
		
		if(plotTypeStdOut.isEmpty()) {textFlowDisplay.getChildren().add(new Text("No available plot for this file type."));return;}
		
		String plotType = comboPlot.getSelectionModel().getSelectedItem();
		
		if(plotType==null) return;
		
		lineChart.getData().clear();
		
		ArrayList<ArrayList<Double>> energyTmp = fileData.getEnergyArray();
		

		if(plotType.equals("SCF E conv")) {
			xAxis.setLabel("SCF Iterations");
			yAxis.setLabel("Total Energy (Ry)");
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
	        dataSeries1.setName("SCF Energy Convergence");
	        if(!energyTmp.isEmpty()) {
				ArrayList<Double> scfTmp = energyTmp.get(energyTmp.size()-1);
				if(scfTmp.isEmpty() && energyTmp.size()>=2) {scfTmp = energyTmp.get(energyTmp.size()-2);}
				for(int i=0;i<scfTmp.size();i++) {
			        dataSeries1.getData().add(new Data<Double, Double>( (double) i+1, scfTmp.get(i)));
				}
				//dataSeries1.getData().add(new Data<Double, Double>( 0.0, -20.0));
	        }
	        lineChart.getData().add(dataSeries1);
		}
		else if(plotType.equals("OPT E conv")) {
			xAxis.setLabel("Optimization Steps");
			yAxis.setLabel("Total Energy (Ry)");
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
	        dataSeries1.setName("Optimization Energy Convergence");
			
			for(int i=0;i<energyTmp.size();i++) {
				if(energyTmp.get(i).size()>0) {
					Double dbTmp = energyTmp.get(i).get(energyTmp.get(i).size()-1);
					if(dbTmp!=null) {dataSeries1.getData().add(new Data<Double, Double>( (double) i+1, dbTmp));}
				}
			}
			lineChart.getData().add(dataSeries1);
		}
		else if(plotType.equals("OPT F conv")) {
			plotArray(fileData.getTotalForce(), "Optimization Steps", "Total Force (Ry/Bohr)","Optimization Force Convergence",false);
		}
		else if(plotType.equals("OPT P conv")) {
			plotArray(fileData.getTotalPressure(), "Optimization Steps", "Pressure (kbar)","Optimization Pressure/Stress Convergence",false);
		}
		else if(plotType.equals("Ekin")) {
			plotArray(fileData.getDataMd().get(0), fileData.getDataMd().get(1),
					"Time/ps", "Ekin (kinetic energy)/Ry","Kinetic energy",false);
		}
		else if(plotType.equals("Temperature")) {
			plotArray(fileData.getDataMd().get(0), fileData.getDataMd().get(2),
					"Time/ps", "T (temperature)/K","Temperature",false);
		}
		else if(plotType.equals("Ekin + Etot")) {
			plotArray(fileData.getDataMd().get(0), fileData.getDataMd().get(3),
					"Time/ps", "Totoal energy (Ekin + Etot)/Ry","Total energy (should be constant)",false);
		}
        
        displayScroll.setContent(lineChart);

	}
	private void plotArray(ArrayList<Double> dataY, String xlabel, String ylabel, String titleStr, boolean boolClear) {
		if(boolClear) {lineChart.getData().clear();}
		if(dataY==null) {return;}
		xAxis.setLabel(xlabel);
		yAxis.setLabel(ylabel);
		Series<Double,Double> dataSeries1 = new Series<Double, Double>();
        dataSeries1.setName(titleStr);
		
		for(int i=0;i<dataY.size();i++) {
			if(dataY.get(i)==null) {continue;}
			dataSeries1.getData().add(new Data<Double, Double>( (double) i+1, dataY.get(i)));
		}
		lineChart.getData().add(dataSeries1);
	}
	private void plotArray(ArrayList<Double> dataX, ArrayList<Double> dataY, String xlabel, String ylabel, String titleStr, boolean boolClear) {
		if(boolClear) {lineChart.getData().clear();}
		if(dataX == null || dataY == null) {return;}
		xAxis.setLabel(xlabel);
		yAxis.setLabel(ylabel);
		Series<Double,Double> dataSeries1 = new Series<Double, Double>();
        dataSeries1.setName(titleStr);
		
		for(int i=0;i<Math.min(dataX.size(), dataY.size());i++) {
			if(dataX.get(i)==null || dataX.get(i).isNaN() ||
					dataY.get(i)==null || dataY.get(i).isNaN()) {continue;}
			dataSeries1.getData().add(new Data<Double, Double>( dataX.get(i), dataY.get(i)));
		}
		lineChart.getData().add(dataSeries1);
	}
	private boolean loadFile() {
		//false is fail to load

		buttonSaveGeo.setDisable(true);
		String strTmp1 = checkErrors();
		if(strTmp1!=null && !strTmp1.isEmpty()) {showCannotLoad("Cannot load file. "+strTmp1);return false;}

		if(fileCategory.equals(EnumFileCategory.stdout)) {
			String msg = fileData.loadStdOut(inoutFiles);
			if(fileData.isOpt&&fileData.isOptFinished) {buttonSaveGeo.setDisable(false);}
			if(!msg.isEmpty()) {showCannotLoad(msg);return false;}
		}
		else if(fileCategory.equals(EnumFileCategory.dos)){
			return fileData.loadDOS(inoutFiles);
		}
		else if(fileCategory.equals(EnumFileCategory.bandsDatGnu)) {
			boolean blTmp = fileData.loadBands(inoutFiles);
			//kpointName.clear();
			ObservableList<String> obsTmp = FXCollections.observableArrayList();
			for(int i=0;i<fileData.getBandsHighSymmetryK().size();i++) {
				//kpointName.add("");
				obsTmp.add(Integer.toString(i+1));
			}
			comboHighSymK.setItems(obsTmp);
			comboHighSymK.getSelectionModel().select(0);
			return blTmp;
		}
		else if(fileCategory.equals(EnumFileCategory.tddftPlotSDat)) {
			return fileData.loadTddft(inoutFiles);
		}
		return true;
	}
	private void showCannotLoad(String msg) {
		displayScroll.setContent(textFlowDisplay);
		textFlowDisplay.getChildren().clear();
		textFlowDisplay.getChildren().add(new Text(msg));
	}
	private String checkErrors() {
		if(fileCategory==null) {return "Error: file category is null. Check code!";}
		if(fileCategory.equals(EnumFileCategory.directory)) {return "Target file is a directory.";}
		if(fileCategory.equals(EnumFileCategory.save)) {return "Target file is quantumVITAS save file.";}
		if(inoutFiles==null || !inoutFiles.canRead()) {return "Error: cannot read file.";}
		return "";
	}
	private void readTextFileToTextFlow() {
		textFlowDisplay.getChildren().clear();
		String strTmp1 = checkErrors();
		if(strTmp1!=null && !strTmp1.isEmpty()) {textFlowDisplay.getChildren().add(new Text(strTmp1));return;}
		
		boolean boolHighLight = false;
		if(EnumFileCategory.stdin.equals(fileCategory)) {boolHighLight=true;}
		
		try {
//			String data = new String(Files.readAllBytes(inoutFiles.toPath()));
//			textFlowDisplay.getChildren().add(new Text(data));
			LineNumberReader count1 = new LineNumberReader(new FileReader(inoutFiles));
			while (count1.skip(Long.MAX_VALUE) > 0)
		    {
				// Loop just in case the file is > Long.MAX_VALUE or skip() decides to not read the entire file
		    }
			int totalLineNum = count1.getLineNumber() + 1;
			count1.close();
			//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", totalLineNum+"");
			Text txtTmp;
			txtTmp = new Text(Integer.toString(totalLineNum)+" lines in total.\n\n");
			txtTmp.setFill(Color.YELLOWGREEN);
			textFlowDisplay.getChildren().add(txtTmp);
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    
		    int lineCount=0;
		    boolean flagSkip = false;
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	if(lineCount > ProgrammingConsts.maxLinesShownInText && lineCount < totalLineNum-ProgrammingConsts.maxLinesShownInText){
		    		if(!flagSkip) {
		    			textFlowDisplay.getChildren().add(
		    					new Text("------------------------------+------------------------+------------------------------\n"+
		    							 "------------------------------+------------------------+------------------------------\n"+
		    							 "------------------------------+-------skip "+
		    							 Integer.toString(totalLineNum-2*ProgrammingConsts.maxLinesShownInText)+" lines-------+------------------------------\n"+
		    							 "------------------------------+------------------------+------------------------------\n"+
		    							 "------------------------------+------------------------+------------------------------\n"));
		    		}
		    		flagSkip = true;
		    		continue;
	    		}
		    	
		    	txtTmp = new Text(strTmp+"\n");
		    	if(boolHighLight) {
			    	if(strTmp!=null && strTmp.contains("calculation")&& strTmp.contains("=")) {txtTmp.setFill(Color.BLUE);}
			    	if(strTmp!=null && containsSectionName(strTmp) && !strTmp.contains("=")) {txtTmp.setFill(Color.GREEN);}
		    	}
		    	textFlowDisplay.getChildren().add(txtTmp);
		    }
		    
		    sc.close();
		    
		    if(lineCount==0) {
		    	textFlowDisplay.getChildren().add(new Text("No normal lines detected. File empty or binary file."));
		    }
		} catch (IOException e) {
			e.printStackTrace();
		} 
	}
	private boolean containsSectionName(String stTmp) {
		if(stTmp==null || stTmp.isEmpty()) return false;
		String newstTmp = stTmp.replaceAll("\\s+","").toLowerCase();//remove all whitespaces and to lower case
		List<String> enumValues1 = Stream.of(EnumNameList.values())
                .map(EnumNameList::toString)
                .collect(Collectors.toList());
		List<String> enumValues2 = Stream.of(EnumCard.values())
                .map(EnumCard::toString)
                .collect(Collectors.toList());
		for (String st : enumValues1) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		for (String st : enumValues2) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		return false;
		
	}
	private File getProjectFolder() {
		String wsp = mainClass.projectManager.workSpacePath;
		String pj = mainClass.projectManager.getActiveProjectName();
		if(wsp==null || pj==null || pj.isEmpty()) return null;
		return new File(new File(wsp),pj);
	}
	private boolean checkIdentity(ObservableList<String> lst1, ObservableList<String> lst2) {
		if(lst1==null && lst2==null) {return true;}//both null
		else if(lst1==null || lst2==null) {return false;}//only one is null
		else {//both not null
			if(lst1.size()!=lst2.size()) {return false;}
			else {
				for(int i=0;i<lst1.size();i++) {
					if(!Objects.equals(lst1.get(i),lst2.get(i))) {return false;}
				}
				return true;
			}
		}
	}

}

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

import java.io.FileReader;
import java.io.IOException;
import java.io.LineNumberReader;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.ResourceBundle;
import java.util.Scanner;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.scene.Node;
import javafx.scene.chart.XYChart.Data;
import javafx.scene.chart.XYChart.Series;
import javafx.scene.control.ScrollPane.ScrollBarPolicy;
import javafx.scene.layout.AnchorPane;
import javafx.scene.paint.Color;
import javafx.scene.text.Text;
import com.consts.Constants.EnumAnalysis;
import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumFileCategory;
import com.consts.Constants.EnumNameList;
import com.consts.Constants.EnumStep;
import com.programconst.DefaultFileNamesQE;
import com.programconst.ProgrammingConstsQE;
import app.input.Kpoint;
import core.app.centerwindow.OutputViewerController;
import core.app.input.InputGeoController;
import core.com.programconst.ProgrammingConsts;
import core.main.MainClass;

public class OutputViewerControllerQE extends OutputViewerController{
    
    private final ArrayList<String> plotTypeDos;
    
    private ArrayList<String> plotTypeStdOut;
    
    private ArrayList<String> plotTypeProjBands;
    
    private double markerScale = 2.0;
    		
    public OutputViewerControllerQE(MainClass mc, InputGeoController contGeo){
    	super(mc,contGeo);
    	
    	plotTypeDos = new ArrayList<String>() {
    		/**
			 * 
			 */
			private static final long serialVersionUID = 4387010690557940911L;
			{
	    		add("DOS"); //0
	    		add("Integrated DOS"); //1 
    		}
		};
		plotTypeStdOut = new ArrayList<String>();
		plotTypeProjBands = new ArrayList<String>();
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		super.initialize(arg0, arg1);
		
		textMarkerScale.setText(Double.toString(markerScale));
		
		toggleShiftFermi.selectedProperty().addListener((ov, oldVal, newVal) -> {
			if(EnumAnalysis.plot2D.equals(comboAnalysis.getSelectionModel().getSelectedItem())) {
				updateIoDisplay();
			}
		});
		setToggleElementOrAtom(false);
		toggleElementOrAtom.selectedProperty().addListener((ov, oldVal, newVal) -> {
			setToggleElementOrAtom(newVal);
			if(newVal!=null) {updateIoDisplay();}
		});
		comboHighSymK.getSelectionModel().selectedIndexProperty().addListener((ov, oldTab, newTab) -> {
			if(fileData==null) {return;}
			if(EnumFileCategory.bandsDatGnu.equals(fileCategory) || EnumFileCategory.pbands.equals(fileCategory)) {
				int selectInd = (int)newTab;

				if(selectInd<0 || selectInd>=fileData.getBandsHighSymmetryK().size()) {return;} 
				labelK.setText("k="+fileData.getBandsHighSymmetryK().get(selectInd)
						+",x="+fileData.getBandsHighSymmetryKXCoor().get(selectInd));
				//textLabelK.setText(kpointName.get(selectInd));
			}
			else if(EnumFileCategory.phononBandsGnu.equals(fileCategory)) {
				int selectInd = (int)newTab;

				if(selectInd<0 || selectInd>=fileData.getPhononK().size()) {return;} 
				Kpoint kp = fileData.getPhononK().get(selectInd);
				labelK.setText("k=("+kp.getKx()+","+kp.getKy()+","+kp.getKz()+"),"
						+(kp.getLabel().isEmpty()?"":":")+kp.getLabel());
			}
			
		});
		textMarkerScale.textProperty().addListener((ov, oldTab, newTab) -> {
			try {
				Double dbTmp = Double.valueOf(newTab);
				if(dbTmp!=null && dbTmp>=0) {
					markerScale = dbTmp;
					textMarkerScale.setStyle("-fx-background-color: white;");
					updateIoDisplay();
				}
				else {textMarkerScale.setStyle("-fx-background-color: red;");}
			}
			catch(Exception e) {
				textMarkerScale.setStyle("-fx-background-color: red;");
			}
		});
//		buttonSetLabelK.setOnAction((event) -> {
//			if(fileData==null || !EnumFileCategory.bandsDatGnu.equals(fileCategory)) {return;}
//			int selectInd = comboHighSymK.getSelectionModel().getSelectedIndex();
//			if(selectInd<0 || selectInd>=kpointName.size()) {return;} 
//			kpointName.set(selectInd, textLabelK.getText());
//			this.plot2dBands();
//		});
		//comboPlot.setVisible(false);labelPlot.setVisible(false);
		
	}
	private void setToggleElementOrAtom(Boolean bl) {
		if(bl==null) {return;}
		toggleElementOrAtom.setSelected(bl);
		if(bl) {toggleElementOrAtom.setText("per atom");}
		else {toggleElementOrAtom.setText("per element");}
	}
	@Override
	protected boolean isFileImportant(String item) {
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
        boolean isPhonon = (calcFolder!=null
        		&& item.contains(EnumStep.PH.toString())
        		&& item.endsWith(ProgrammingConsts.stdoutExtension));
        boolean isNeb = (calcFolder!=null 
        		&& item.contains(EnumStep.NEB.toString())
        		&& item.endsWith(ProgrammingConsts.stdoutExtension));
        return (item.endsWith(ProgrammingConstsQE.dosExtension)
        		|| (item.contains(DefaultFileNamesQE.bandsDatGnu) && item.endsWith(".gnu"))
        		|| (item.startsWith(DefaultFileNamesQE.filproj+".") && item.contains("projwfc"))
        		|| item.contains(DefaultFileNamesQE.tddftPlotSDat)
        		|| isScf || isOpt || isMd || isNeb
        		|| (item.contains(DefaultFileNamesQE.flfrq)&&item.endsWith(ProgrammingConstsQE.phononGnuExtension))
        		|| isPhonon
        		);
	}
	@Override
	protected void updateIoDisplay() {
		buttonShowMarker.setDisable(false);
		textMarkerScale.setDisable(true);
		toggleElementOrAtom.setDisable(true);
		//ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "updateIoDisplay involked.", false);
		
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
			else if(fileCategory.equals(EnumFileCategory.dos) || fileCategory.equals(EnumFileCategory.pdosall)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dDos();}//efficient
			}
			else if(fileCategory.equals(EnumFileCategory.tddftPlotSDat)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dTddft();}//efficient
			}
			else if(fileCategory.equals(EnumFileCategory.bandsDatGnu)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {comboPlot.getItems().clear();plot2dBands();}//efficient
			}
			else if(fileCategory.equals(EnumFileCategory.pbands)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plot2dProjBands();}//efficient
			}
			else if(fileCategory.equals(EnumFileCategory.phononBandsGnu)){
				if(analTmp.equals(EnumAnalysis.info)) {textFlowDisplay.getChildren().add(new Text(fileData.toString()));}
				else if(analTmp.equals(EnumAnalysis.plot2D)) {plotPhBands();}//efficient
			}
			else {
				textFlowDisplay.getChildren().add(new Text("Analysis is not available for this file type."));
			}
		}
	}
	
	private void plotPhBands() {
		comboPlot.getItems().clear();
		
		//high symmetry k points
		hboxBandsToolbar.setVisible(true);
	
		buttonShowMarker.setSelected(false);
		lineChart.getData().clear();
		
		ArrayList<ArrayList<Double>> pdat = fileData.getPhononDat();
		
		if(pdat.isEmpty()) {return;}
		
		xAxis.setLabel("k");
		yAxis.setLabel("Frequency (cm-1)");
		
		minY = 10000.0;
		maxY = -10000.0;
		
		ArrayList<Data<Double, Double>> lstData = new ArrayList<Data<Double, Double>>();
		
		//k,j,i
		//bands,k points,spins (1 or 2)
		for(int i=1;i<pdat.get(0).size();i++) {//different bands (y axis). Starting from 1 because 0 is x axis
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			lstData.clear();
			for(int j=0;j<pdat.size();j++) {
				if(pdat.get(j).size()<=i) {break;}//a certain row does not have enough numbers
				lstData.add(new Data<Double, Double>(pdat.get(j).get(0), pdat.get(j).get(i)));
				if(pdat.get(j).get(i)>maxY) {maxY=pdat.get(j).get(i);}
				if(pdat.get(j).get(i)<minY) {minY=pdat.get(j).get(i);}
			}
			dataSeries1.getData().addAll(lstData);
			lineChart.getData().add(dataSeries1);
        }
		
		int i=0;
		int nkPassed = 0;
		for(Kpoint kp : fileData.getPhononK()) {
			i++;
			//high symmetry q points
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			lineChart.getData().add(dataSeries1);
			double dbTmp = pdat.get(nkPassed).get(0);
			nkPassed+=kp.getNk();
			dataSeries1.getData().add(new Data<Double, Double>(dbTmp, minY));
			dataSeries1.getData().add(new Data<Double, Double>(dbTmp, maxY));

			dataSeries1.setName("q"+Integer.toString(i)+"=("+
					kp.getKx()+","+kp.getKy()+","+kp.getKz()+"),x="+dbTmp+(kp.getLabel().isEmpty()?"":":")+kp.getLabel());
		}

        displayScroll.setContent(lineChart);
	}
	private void plot2dProjBands() {
		plot2dBands();
		buttonShowMarker.setSelected(true);
		buttonShowMarker.setDisable(true);//do not allow user to turn off markers
		textMarkerScale.setDisable(false);
		toggleElementOrAtom.setDisable(false);
		Series<Double, Double> series;
		Data<Double, Double> data;
		
		ArrayList<ArrayList<ArrayList<Double>>> projBandsArray;
		if(toggleElementOrAtom.isSelected()) {
			projBandsArray = fileData.getProjBandsArray();
			plotTypeProjBands = fileData.getProjBandsHeader();//reference type, should NEVER clear or modify here
		}
		else {
			projBandsArray = fileData.getProjBandsElementsArray();
			plotTypeProjBands = fileData.getProjBandsElementsHeader();//reference type, should NEVER clear or modify here
		}
		
		if(!isSameTypeStdout(plotTypeProjBands)) {
			comboPlot.getItems().clear();
			comboPlot.getItems().addAll(plotTypeProjBands);
			comboPlot.getSelectionModel().select(0);
		}
		
		int projIndex = comboPlot.getSelectionModel().getSelectedIndex();
		
		//ShowAlert.showAlert("Debug", ""+projIndex);
		
		if(projIndex < 0 || projIndex >= projBandsArray.size() || projIndex >= plotTypeProjBands.size()) {
			return;
		}
		
		ArrayList<ArrayList<Double>> projBands = projBandsArray.get(projIndex);
		String projHeader = plotTypeProjBands.get(projIndex);
		
		for (int i=0;i<lineChart.getData().size();i++) {
			//different bands AND OTHER HELPING LINES
			series = lineChart.getData().get(i);
			
			for (int j=0;j<series.getData().size();j++) {
				//different k points
				//ShowAlert.showAlert("Debug", ""+lineChart.getData().size()+","+series.getData().size());
				data = series.getData().get(j);
				// this node is StackPane
				Node node = data.getNode();
				//ShowAlert.showAlert("Debug", node.toString());
				if(node!=null) {
					try {
						node.setScaleX(markerScale*projBands.get(j).get(i));
						node.setScaleY(markerScale*projBands.get(j).get(i));
					}
					catch(Exception e) {
						node.setVisible(false);
						node.setVisible(false);
					}
				}
			}
		}
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
		
		double dbShift = (toggleShiftFermi.isSelected() && fermiDos!=null)?fermiDos:0.0;
		
		//k,j,i
		//bands,k points,spins (1 or 2)
		ArrayList<Data<Double, Double>> lstData = new ArrayList<Data<Double, Double>>();
		
		for(int k=0;k<bandsDatArray.size();k++) {//different bands
			if(bandsDatArray.get(k).isEmpty()) {continue;}
			lstData.clear();
			
			for(int i=1;i<bandsDatArray.get(k).get(0).size();i++) {//different columns (spins). Starting from 1 because 0 is xaxis
				
				Series<Double,Double> dataSeries1 = new Series<Double, Double>();
				lineChart.getData().add(dataSeries1);
				
				dataSeries1.setName("Band "+Integer.toString(k+1));
	
				for(int j=0;j<bandsDatArray.get(k).size();j++) {//different k points
					
					if(bandsDatArray.get(k).get(j).size() <= i) {break;}//a certain row does not have enough numbers
					lstData.add(new Data<Double, Double>(bandsDatArray.get(k).get(j).get(0), bandsDatArray.get(k).get(j).get(i)-dbShift));
					
					//dt.getNode().setStyle("-fx-background-color: #4a86e8;");
					
					if(bandsDatArray.get(k).get(j).get(i)-dbShift>maxY) {maxY=bandsDatArray.get(k).get(j).get(i)-dbShift;}
					if(bandsDatArray.get(k).get(j).get(i)-dbShift<minY) {minY=bandsDatArray.get(k).get(j).get(i)-dbShift;}
					if(bandsDatArray.get(k).get(j).get(0)>maxX) {maxX=bandsDatArray.get(k).get(j).get(0);}
					if(bandsDatArray.get(k).get(j).get(0)<minX) {minX=bandsDatArray.get(k).get(j).get(0);}
				}
				
				dataSeries1.getData().addAll(lstData);
				//dataSeries1.getNode().setStyle("-fx-stroke: #4a86e8;");
				
				lineChart.getStyleClass().add("chart-series-line");
	        }
		}
		
		//the following must be plot AFTER the bands, otherwise need to modify plot2dProjBands()
		//Fermi energy
		if(fermiDos!=null) {
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			dataSeries1.getData().add(new Data<Double, Double>(minX, fermiDos-dbShift));
			dataSeries1.getData().add(new Data<Double, Double>(maxX, fermiDos-dbShift));
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
		comboPlot.getItems().clear();
		
		buttonShowMarker.setSelected(false);
		
		lineChart.getData().clear();
		
		
		ArrayList<ArrayList<Double>> tddftArray = fileData.getTddftArray();
		ArrayList<String> tddftHeader = fileData.getTddftHeader();
		
		if(tddftArray.isEmpty()) {return;}
		
		xAxis.setLabel(tddftHeader.size()>0 ? tddftHeader.get(0):"Unknown (1st column)");
		yAxis.setLabel(tddftHeader.size()>1 ? tddftHeader.get(1):"Unknown (2nd column)");
		
		ArrayList<Data<Double, Double>> lstData = new ArrayList<Data<Double, Double>>();
		
		for(int i=1;i<tddftArray.get(0).size();i++) {//different columns (y axis). Starting from 1 because 0 is xaxis
			lstData.clear();
			
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			String headerTmp = (tddftHeader.size()>i ? tddftHeader.get(i):"Unknown ("+Integer.toString(i)+"th column)");
			dataSeries1.setName(headerTmp);
			for(int j=0;j<tddftArray.size();j++) {
				if(tddftArray.get(j).size()<=i) {break;}//a certain row does not have enough numbers
				lstData.add(new Data<Double, Double>(tddftArray.get(j).get(0), 
						tddftArray.get(j).get(i)));
			}
			dataSeries1.getData().addAll(lstData);
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
		
		minY = 10000.0;
		maxY = -10000.0;
		
		double dbShift = (toggleShiftFermi.isSelected() && fermiDos!=null)?fermiDos:0.0;
		
		//ShowAlert.showAlert("Debug", ""+dosArray.size());
		ArrayList<Data<Double, Double>> lstData = new ArrayList<Data<Double, Double>>();
		
		for(int i=1;i<dosArray.get(0).size();i++) {//different columns (y axis). Starting from 1 because 0 is xaxis
			lstData.clear();
			
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			String headerTmp = (dosHeader.size()>i ? dosHeader.get(i):"Unknown ("+Integer.toString(i)+"th column)");
			dataSeries1.setName(headerTmp);
			if(boolInteg != headerTmp.toLowerCase().contains("int") ) {continue;}

			for(int j=0;j<dosArray.size();j++) {
				if(dosArray.get(j).size()<=i) {break;}//a certain row does not have enough numbers
				
				lstData.add(new Data<Double, Double>(dosArray.get(j).get(0)-dbShift, dosArray.get(j).get(i)));
				
				if(dosArray.get(j).get(i)>maxY) {maxY=dosArray.get(j).get(i);}
				if(dosArray.get(j).get(i)<minY) {minY=dosArray.get(j).get(i);}
			}
			
			dataSeries1.getData().addAll(lstData);
			
			//ShowAlert.showAlert("Debug", ""+i+"th,finished!");
			lineChart.getData().add(dataSeries1);
			//ShowAlert.showAlert("Debug", ""+i+"th,loaded!");
        }
		
		//ShowAlert.showAlert("Debug", ""+dosArray.size()+",finished!");
		
		//Fermi energy
		if(fermiDos!=null) {
			Series<Double,Double> dataSeries1 = new Series<Double, Double>();
			dataSeries1.getData().add(new Data<Double, Double>(fermiDos-dbShift, minY));
			dataSeries1.getData().add(new Data<Double, Double>(fermiDos-dbShift, maxY));
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
			if(!fileData.getAbsoluteMag().isEmpty() || !fileData.getTotalMag().isEmpty()) {
				plotTypeStdOut.add("OPT magnet");
			}
			plotTypeStdOut.add("OPT F conv");
			if(!fileData.getTotalPressure().isEmpty()) {
				plotTypeStdOut.add("OPT P conv");
			}
		}
		if(fileData.isMD) {
			plotTypeStdOut.add("Ekin");//if change here, remember to change later in this function
			plotTypeStdOut.add("Temperature");
			plotTypeStdOut.add("Ekin + Etot");
		}
		if(fileData.isNeb) {
			plotTypeStdOut.add("E, last step");//if change here, remember to change later in this function
			plotTypeStdOut.add("Error, last step");
			plotTypeStdOut.add("Activation E");
		}
		if(fileData.hasScf) {
			plotTypeStdOut.add("SCF E conv");
			if(!fileData.getAbsoluteMag().isEmpty() || !fileData.getTotalMag().isEmpty()) {
				plotTypeStdOut.add("SCF magnet");
			}
			if(fileData.isHybrid) {
				plotTypeStdOut.add("Hybrid steps");
			}
		}
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
		ArrayList<ArrayList<Double>> absMagTmp = fileData.getAbsoluteMag();
		ArrayList<ArrayList<Double>> magTmp = fileData.getTotalMag();
		ArrayList<ArrayList<Double>> magTmpy = fileData.getTotalMagy();
		ArrayList<ArrayList<Double>> magTmpz = fileData.getTotalMagz();

		if(plotType.equals("SCF E conv")) {
			plotScfArray(energyTmp, "SCF Iterations", "Total Energy (Ry)", "SCF Energy Convergence");
		}
		else if(plotType.equals("SCF magnet")){
			plotScfArray(absMagTmp, "SCF Iterations", "Magnetic moment (uB)", "absolute magnetic moment");
			plotScfArray(magTmp, "SCF Iterations", "Magnetic moment (uB)", (magTmpy.isEmpty()?"total magnetic moment":"total magnetic moment (x)"));
			plotScfArray(magTmpy, "SCF Iterations", "Magnetic moment (uB)", "total magnetic moment (y)");
			plotScfArray(magTmpz, "SCF Iterations", "Magnetic moment (uB)", "total magnetic moment (z)");
		}
		else if(plotType.equals("Hybrid steps")) {
			plotOptArray(energyTmp, "Hybrid Steps", "Total Energy (Ry)", "Hybrid Functional Energy Convergence");
		}
		else if(plotType.equals("OPT E conv")) {
			plotOptArray(energyTmp, "Optimization Steps", "Total Energy (Ry)", "Optimization Energy Convergence");
		}
		else if(plotType.equals("OPT magnet")) {
			plotOptArray(absMagTmp, "Optimization Steps", "Magnetic moment (uB)", "absolute magnetic moment");
			plotOptArray(magTmp, "Optimization Steps", "Magnetic moment (uB)", (magTmpy.isEmpty()?"total magnetic moment":"total magnetic moment (x)"));
			plotOptArray(magTmpy, "Optimization Steps", "Magnetic moment (uB)", "total magnetic moment (y)");
			plotOptArray(magTmpz, "Optimization Steps", "Magnetic moment (uB)", "total magnetic moment (z)");
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
		else if(plotType.equals("E, last step")) {
			plotScfArray(fileData.getNebEnergy(), "Image index", "Energy (eV)", "Total energy of each image");
		}
		else if(plotType.equals("Error, last step")) {
			plotScfArray(fileData.getNebError(), "Image index", "Error (eV/A)", "Error of each image");
		}
		else if(plotType.equals("Activation E")) {
			plotArray(fileData.getNebBarrierFwd(), "NEB Steps", "Activation energy (eV)", "Energy barrier forward",false);
			plotArray(fileData.getNebBarrierBwd(), "NEB Steps", "Activation energy (eV)", "Energy barrier backward",false);
		}
        
        displayScroll.setContent(lineChart);

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
	@Override
	protected boolean loadFile() {
		//false is fail to load

		buttonSaveGeo.setDisable(true);
		String strTmp1 = checkErrors();
		if(strTmp1!=null && !strTmp1.isEmpty()) {showCannotLoad("Cannot load file. "+strTmp1);return false;}

		if(fileCategory.equals(EnumFileCategory.stdout)) {
			String msg = fileData.loadStdOut(inoutFiles);
			if(fileData.isOpt&&fileData.isOptFinished) {buttonSaveGeo.setDisable(false);}
			if(!msg.isEmpty()) {showCannotLoad(msg);return false;}
		}
		else if(fileCategory.equals(EnumFileCategory.dos) || fileCategory.equals(EnumFileCategory.pdosall)){
			return fileData.loadDOS(inoutFiles);
		}
		else if(fileCategory.equals(EnumFileCategory.bandsDatGnu)) {
			boolean blTmp = fileData.loadBands(inoutFiles);
			setHighSymK();
			
			return blTmp;
		}
		else if(fileCategory.equals(EnumFileCategory.pbands)) {
			boolean blTmp = fileData.loadProjBands(inoutFiles);
			setHighSymK();
			
			return blTmp;
		}
		else if(fileCategory.equals(EnumFileCategory.phononBandsGnu)) {
			boolean blTmp = fileData.loadPhononBands(inoutFiles);
			//kpointName.clear();
			ObservableList<String> obsTmp = FXCollections.observableArrayList();
			for(int i=0;i<fileData.getPhononK().size();i++) {//do not use setHighSymK()
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
	private void setHighSymK() {
		//kpointName.clear();
		ObservableList<String> obsTmp = FXCollections.observableArrayList();
		for(int i=0;i<fileData.getBandsHighSymmetryK().size();i++) {
			//kpointName.add("");
			obsTmp.add(Integer.toString(i+1));
		}
		comboHighSymK.setItems(obsTmp);
		comboHighSymK.getSelectionModel().select(0);
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

	@Override
	protected void getFileCategory(String newTab) {
		if(newTab.endsWith(ProgrammingConsts.stdinExtension)) {fileCategory = EnumFileCategory.stdin;}
		else if(newTab.endsWith(ProgrammingConsts.stdoutExtension)) {fileCategory = EnumFileCategory.stdout;}
		else if(newTab.endsWith(ProgrammingConsts.stderrExtension)) {fileCategory = EnumFileCategory.stderr;}
		else if(newTab.endsWith(ProgrammingConstsQE.dosExtension)) {fileCategory = EnumFileCategory.dos;}
		else if(newTab.contains(DefaultFileNamesQE.bandsDatGnu) && newTab.endsWith(".gnu")) {fileCategory = EnumFileCategory.bandsDatGnu;}
		else if(newTab.contains(DefaultFileNamesQE.tddftPlotSDat)){fileCategory = EnumFileCategory.tddftPlotSDat;}
		else if(newTab.contains(DefaultFileNamesQE.flfrq)&&newTab.endsWith(ProgrammingConstsQE.phononGnuExtension)){fileCategory = EnumFileCategory.phononBandsGnu;}
		else if(newTab.contains(DefaultFileNamesQE.calcSaveFile)||newTab.contains(DefaultFileNamesQE.projSaveFile)) 
		{fileCategory = EnumFileCategory.save;}
		else if(newTab.startsWith(DefaultFileNamesQE.filpdos+".")) {fileCategory = EnumFileCategory.pdosall;}
		else if(newTab.startsWith(DefaultFileNamesQE.filproj+".") && newTab.contains("projwfc")) {fileCategory = EnumFileCategory.pbands;}
		else if(newTab.contains(".xml")) {fileCategory = EnumFileCategory.xmlout;}
		else if(newTab.toLowerCase().contains("crash")) {fileCategory = EnumFileCategory.crash;}
		else if(inoutFiles.isDirectory()) {fileCategory = EnumFileCategory.directory;}
		else {fileCategory = EnumFileCategory.unknown;}
		
	}

	@Override
	protected void updateComboAnalysis() {
		if(fileCategory!=null) {
			comboAnalysis.getItems().addAll(EnumAnalysis.text);//always has the option of show in text
			if(EnumFileCategory.stdout.equals(fileCategory) || EnumFileCategory.dos.equals(fileCategory) 
					|| EnumFileCategory.bandsDatGnu.equals(fileCategory) || EnumFileCategory.tddftPlotSDat.equals(fileCategory)
					|| EnumFileCategory.phononBandsGnu.equals(fileCategory) || EnumFileCategory.pdosall.equals(fileCategory)
					|| EnumFileCategory.pbands.equals(fileCategory)) {
				comboAnalysis.getItems().addAll(EnumAnalysis.info);
				if(!fileData.isPH) {
					comboAnalysis.getItems().addAll(EnumAnalysis.plot2D);
				}
			}
			if(fileData.isMD || fileData.isOpt) {comboAnalysis.getItems().addAll(EnumAnalysis.plot3D);}
			
//			if(analTmp!=null && comboAnalysis.getItems().contains(analTmp)) {
//				//select back the choice before
//				comboAnalysis.getSelectionModel().select(analTmp);
//			}
//			else {
//				//select text first if there has been no selection
//				if(comboAnalysis.getItems().contains(EnumAnalysis.plot2D)) {
//					comboAnalysis.getSelectionModel().select(EnumAnalysis.plot2D);
//				}
//				else {
//					comboAnalysis.getSelectionModel().select(EnumAnalysis.text);
//				}
//			}
			if(EnumFileCategory.stdout.equals(fileCategory) && !this.fileData.isMD  && !this.fileData.isOpt  
					&& !this.fileData.hasScf && !this.fileData.isNeb) {
				comboAnalysis.getSelectionModel().select(EnumAnalysis.info);//no need to check existence
			}
			else {
				comboAnalysis.getSelectionModel().select(EnumAnalysis.plot2D);//no need to check existence
			}
			
			if(comboAnalysis.getSelectionModel().getSelectedIndex()==-1) {comboAnalysis.getSelectionModel().select(EnumAnalysis.text);}
			
			//necessary to always has one selection, so that the efficiency improvement in comboAnalysis works

		}
		
		//not necessary to have updateIoDisplay() here because it will ALWAYS trigger the selection listener of comboAnalysis
		
//		updateIoDisplay();
//		ShowAlert.showAlert(AlertType.INFORMATION, "Debug", "updateIoDisplay involked by listFiles.", false);
		
	}
	

}
